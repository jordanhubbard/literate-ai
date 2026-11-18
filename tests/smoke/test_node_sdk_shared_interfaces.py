"""Shared public bytes keep exact selected provider facts; no runtime grants."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.generation_preparation import (
    LockedComponentNodePreparationAdapter,
    _node_authority_segments,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthorityReaderError,
)
from literate_ai.application.component_generation_context import (
    ComponentGenerationContextError,
    GenerationComplexityBudgetExceeded,
    canonical_direct_interface_sources,
    prepare_component_generation_context,
)
from literate_ai.application.generation_preparation import GenerationPreparationError
from literate_ai.contracts import ContextAuthorityKind, canonical_identity
from tests.smoke.test_node_sdk_cross_language import with_provider
from tests.support.fixtures_test_component_generation_context import (
    _budget,
    _diamond_lock,
    _materialize,
    _named_plan,
)

DIRECT = ContextAuthorityKind.DIRECT_PUBLIC_INTERFACE


class SharedInterfaceContextTests(unittest.TestCase):
    def fixture(self):
        plan, inputs = _materialize(_named_plan(_diamond_lock(), "invoice-cli"))
        public = next(item for item in inputs if item.authority_kind is DIRECT)
        self.assertGreaterEqual(len(plan.direct_generation_edges), 2)
        plan = replace(
            plan,
            generation_key=replace(
                plan.generation_key,
                direct_public_interface_identities=(public.content_identity,),
            ),
            direct_generation_edges=tuple(
                replace(edge, public_interface_identity=public.content_identity)
                for edge in plan.direct_generation_edges
            ),
        )
        sources = sorted(
            {edge.provider_revision for edge in plan.direct_generation_edges},
            key=lambda source: source.uri,
        )
        # Explicit synthetic provider-resolution DATA verifies that attribution
        # preserves unrelated selected identities; it supplies no admission.
        plan = replace(
            plan,
            generation_key=replace(
                plan.generation_key,
                provider_resolution_identities=tuple(
                    sorted(
                        (
                            canonical_identity({"selected": source.uri})
                            for source in sources
                        ),
                        key=lambda value: value.uri,
                    )
                ),
            ),
        )
        public = replace(public, source_component_revision=sources[0])
        inputs = tuple(item for item in inputs if item.authority_kind is not DIRECT)
        return plan, (*inputs, public), sources

    def prepare(self, plan, inputs):
        return prepare_component_generation_context(
            plan,
            framework_envelope=b"trusted shared-interface test envelope",
            authority_segments=inputs,
            budget=_budget(),
        )

    def test_canonical_source_is_independent_of_input_order(self):
        plan, inputs, sources = self.fixture()
        original = plan.to_dict()
        first = self.prepare(plan, inputs)
        second = self.prepare(plan, tuple(reversed(inputs)))
        self.assertEqual(first, second)
        public = [
            segment
            for segment in first.request.context_manifest.segments
            if segment.authority_kind is DIRECT
        ]
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0].source_component_revision, sources[0])
        self.assertEqual(plan.to_dict(), original)

    def test_shared_bytes_do_not_hide_selected_provider_fan_in(self):
        plan, inputs, sources = self.fixture()
        with self.assertRaises(GenerationComplexityBudgetExceeded) as rejected:
            prepare_component_generation_context(
                plan,
                framework_envelope=b"trusted envelope",
                authority_segments=inputs,
                budget=_budget(max_dependency_fan_in=1),
            )
        self.assertEqual(rejected.exception.decision.dependency_fan_in, len(sources))
        self.assertEqual(rejected.exception.decision.violations, ("dependency_fan_in",))
        allowed = self.prepare(plan, inputs)
        self.assertEqual(
            allowed.request.budget_decision.dependency_fan_in, len(sources)
        )

    def test_multiple_requirements_for_one_provider_charge_one_origin(self):
        plan, inputs, sources = self.fixture()
        edges = tuple(
            sorted(
                (
                    replace(edge, provider_revision=sources[0])
                    for edge in plan.direct_generation_edges
                ),
                key=lambda edge: (
                    edge.consumer_revision.uri,
                    edge.provider_revision.uri,
                    edge.requirement_id,
                    edge.kind.value,
                ),
            )
        )
        plan = replace(plan, direct_generation_edges=edges)
        allowed = prepare_component_generation_context(
            plan,
            framework_envelope=b"trusted envelope",
            authority_segments=inputs,
            budget=_budget(max_dependency_fan_in=1),
        )
        self.assertEqual(allowed.request.budget_decision.dependency_fan_in, 1)

    def test_source_projection_is_independent_of_edge_iteration_order(self):
        plan, _inputs, _sources = self.fixture()
        expected = canonical_direct_interface_sources(plan)
        # ComponentGenerationPlan itself requires canonical edge order. Exercise
        # this pure DATA selector's ordering property without forging a valid
        # differently ordered plan or changing request/plan identities.
        reversed_data = SimpleNamespace(
            direct_generation_edges=tuple(reversed(plan.direct_generation_edges))
        )
        self.assertEqual(canonical_direct_interface_sources(reversed_data), expected)

    def test_other_selected_source_and_foreign_source_are_not_representatives(self):
        plan, inputs, sources = self.fixture()
        for source in (sources[-1], canonical_identity("unselected provider")):
            with self.subTest(source=source.uri):
                wrong = replace(inputs[-1], source_component_revision=source)
                with self.assertRaises(ComponentGenerationContextError) as rejected:
                    self.prepare(plan, (*inputs[:-1], wrong))
                self.assertEqual(
                    rejected.exception.code,
                    "generation_context.source_component_mismatch",
                )

    def test_duplicate_missing_and_changed_bytes_remain_refused(self):
        plan, inputs, _sources = self.fixture()
        for rows, code in (
            ((*inputs, inputs[-1]), "generation_context.authority_duplicate"),
            (inputs[:-1], "generation_context.authority_incomplete"),
            (
                (*inputs[:-1], replace(inputs[-1], content=b"different")),
                "generation_context.content_drift",
            ),
        ):
            with self.subTest(code=code):
                with self.assertRaises(ComponentGenerationContextError) as rejected:
                    self.prepare(plan, rows)
                self.assertEqual(rejected.exception.code, code)


class SharedInterfaceProjectionTests(unittest.TestCase):
    def fixture(self, root):
        component, snapshot, execution = with_provider(
            root, second_provider=True, shared_interfaces=True
        )
        plan = next(
            plan
            for plan in execution.generation_plans
            if plan.component_revision == execution.root_revision
        )
        self.assertEqual(len(plan.direct_generation_edges), 2)
        self.assertEqual(len(plan.generation_key.direct_public_interface_identities), 1)
        self.assertEqual(
            plan.generation_key.provider_resolution_identities,
            tuple(
                item.identity for item in snapshot.authority.lock.provider_resolutions
            ),
        )
        node = next(
            node
            for node in snapshot.authority.lock.nodes
            if node.revision.identity == plan.component_revision
        )
        return component, snapshot, plan, node

    def test_real_locked_recipe_deduplicates_only_the_public_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            _component, snapshot, plan, _node = self.fixture(Path(raw))
            original = plan.to_dict()
            projected = LockedComponentNodePreparationAdapter().project(snapshot, plan)
            public = [
                row
                for row in projected.authority_segments
                if row.authority_kind is DIRECT
            ]
            self.assertEqual(len(public), 1)
            self.assertEqual(
                public[0].source_component_revision,
                min(
                    (edge.provider_revision for edge in plan.direct_generation_edges),
                    key=lambda source: source.uri,
                ),
            )
            self.assertIn("shared", public[0].reason)
            self.assertEqual(len(projected.recipe.library_dependencies), 2)
            self.assertEqual(
                {
                    row.provider_component_revision
                    for row in projected.recipe.library_dependencies
                },
                {edge.provider_revision for edge in plan.direct_generation_edges},
            )
            request = prepare_component_generation_context(
                plan,
                framework_envelope=projected.recipe.prompt(
                    include_locked_authority_documents=False
                ).encode(),
                authority_segments=projected.authority_segments,
                budget=_budget(),
            )
            self.assertNotIn(b"PRIVATE_PROVIDER_IMPLEMENTATION", request.prompt)
            self.assertNotIn(b"PRIVATE_PROVIDER_ORACLE", request.prompt)
            self.assertEqual(plan.to_dict(), original)

    def test_nonrepresentative_selected_file_drift_or_removal_refuses(self):
        for action in ("alter", "remove"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as raw:
                component, snapshot, plan, _node = self.fixture(Path(raw))
                sources = {
                    edge.provider_revision for edge in plan.direct_generation_edges
                }
                representative = min(sources, key=lambda source: source.uri)
                provider = next(
                    node.revision
                    for node in snapshot.authority.lock.nodes
                    if node.revision.identity in sources
                    and node.revision.identity != representative
                )
                path = component / provider.coordinate.name / "interfaces/public.md"
                self.assertTrue(path.is_file(), "fault did not locate selected origin")
                if action == "alter":
                    path.write_bytes(b"changed selected nonrepresentative origin")
                else:
                    path.unlink()
                with self.assertRaises(LockedGenerationAuthorityReaderError):
                    LockedComponentNodePreparationAdapter().project(snapshot, plan)

    def test_every_selected_origin_is_read_before_deduplication(self):
        with tempfile.TemporaryDirectory() as raw:
            _component, snapshot, plan, node = self.fixture(Path(raw))
            shared = plan.generation_key.direct_public_interface_identities[0]
            seen = []

            def content(authoring, reference):
                if reference.identity == shared:
                    seen.append(authoring)
                return snapshot.component_content(authoring, reference)

            proxy = SimpleNamespace(
                authority=snapshot.authority, component_content=content
            )
            rows = _node_authority_segments(proxy, node, plan)
            expected = {
                item.revision.authoring_identity
                for item in snapshot.authority.lock.nodes
                if item.revision.identity
                in {edge.provider_revision for edge in plan.direct_generation_edges}
            }
            self.assertEqual(set(seen), expected)
            self.assertEqual(len(seen), 2)
            self.assertEqual(sum(row.authority_kind is DIRECT for row in rows), 1)

    def test_different_bytes_from_nonrepresentative_cannot_be_discarded(self):
        with tempfile.TemporaryDirectory() as raw:
            _component, snapshot, plan, node = self.fixture(Path(raw))
            shared = plan.generation_key.direct_public_interface_identities[0]
            representative = min(
                (edge.provider_revision for edge in plan.direct_generation_edges),
                key=lambda source: source.uri,
            )
            nonrepresentative = next(
                item.revision.authoring_identity
                for item in snapshot.authority.lock.nodes
                if item.revision.identity != representative
                and item.revision.identity
                in {edge.provider_revision for edge in plan.direct_generation_edges}
            )
            seen = []

            def content(authoring, reference):
                value = snapshot.component_content(authoring, reference)
                if reference.identity == shared and authoring == nonrepresentative:
                    seen.append(True)
                    return b"different public bytes"
                return value

            proxy = SimpleNamespace(
                authority=snapshot.authority, component_content=content
            )
            with self.assertRaises(GenerationPreparationError) as rejected:
                _node_authority_segments(proxy, node, plan)
            self.assertEqual(
                rejected.exception.code, "component_preparation.direct_interface_drift"
            )
            self.assertEqual(seen, [True])
