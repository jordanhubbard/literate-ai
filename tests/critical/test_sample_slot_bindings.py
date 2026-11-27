"""Real lock resolution and recipe slot joining with modeled catalog descriptors.

No generation, tool invocation or native sample acceptance is claimed here.
"""

import unittest
from dataclasses import replace
from types import SimpleNamespace

from literate_ai.application.component_lock_resolution import (
    ComponentLockResolver,
    FlavorCandidateInput,
)
from literate_ai.contracts.flavors import (
    CandidateStatus,
    FlavorAxis,
    FlavorCardinality,
    FlavorSlot,
)
from tests.conformance.support.sample_runner import (
    SampleFailure,
    _ordered_selected_flavors,
)
from tests.support.fixtures_test_component_lock_contracts import (
    component_authoring,
    identity,
)
from tests.support.fixtures_test_component_lock_resolution import (
    resolution_plan,
    resolved_node,
)


def catalog_flavor(revision, *, name, axis, value):
    return SimpleNamespace(
        definition=SimpleNamespace(
            primary_axis=axis, coordinate=SimpleNamespace(name=name)
        ),
        descriptor=SimpleNamespace(revision_identity=revision, axis_value=value),
    )


def resolve(plan):
    lock = (
        ComponentLockResolver()
        .resolve(plan, expected_input_evidence_identity=plan.identity)
        .lock
    )
    return SimpleNamespace(lock=lock)


class SampleSlotBindingsTests(unittest.TestCase):
    def paired(self, *, shared_revision=False):
        slots = tuple(
            FlavorSlot(
                slot,
                FlavorAxis.TOOLCHAIN,
                FlavorCardinality.EXACTLY_ONE,
                "portable-application",
            )
            for slot in ("compiler", "package-manager")
        )
        authoring = replace(component_authoring("paired-tools"), flavor_slots=slots)
        revisions = tuple(
            identity("shared" if shared_revision else slot.slot_id) for slot in slots
        )
        node = replace(
            resolved_node(authoring, selected="npm", rejected="other"),
            flavor_candidates=tuple(
                FlavorCandidateInput(
                    slot.slot_id, "npm", revision, CandidateStatus.SELECTED
                )
                for slot, revision in zip(slots, revisions, strict=True)
            ),
        )
        plan = replace(
            resolution_plan(),
            root_authoring_identity=authoring.identity,
            nodes=(node,),
            requirement_providers=(),
        )
        flavors = tuple(
            catalog_flavor(
                revision, name=slot.slot_id, axis=FlavorAxis.TOOLCHAIN, value="npm"
            )
            for slot, revision in zip(slots, revisions, strict=True)
        )
        return authoring, resolve(plan), flavors

    def test_same_axis_value_retains_distinct_exact_slot_revisions(self):
        authoring, authority, flavors = self.paired()
        ordered = _ordered_selected_flavors(authoring, flavors, authority)
        self.assertEqual(
            [(item.flavor, item.slot_ids) for item in ordered],
            [(flavors[0], ("compiler",)), (flavors[1], ("package-manager",))],
        )

    def test_one_exact_revision_can_bind_both_slots(self):
        authoring, authority, flavors = self.paired(shared_revision=True)
        ordered = _ordered_selected_flavors(authoring, flavors[:1], authority)
        self.assertEqual(len(ordered), 1)
        self.assertIs(ordered[0].flavor, flavors[0])
        self.assertEqual(ordered[0].slot_ids, ("compiler", "package-manager"))

    def test_missing_original_revision_refuses_same_target_substitute(self):
        authoring, authority, flavors = self.paired()
        with self.assertRaisesRegex(SampleFailure, "unavailable"):
            _ordered_selected_flavors(authoring, flavors[:1], authority)

    def test_dependency_flavors_never_enter_root_recipe(self):
        plan = resolution_plan()
        authority = resolve(plan)
        authoring = next(
            node.authoring
            for node in plan.nodes
            if node.authoring.identity == plan.root_authoring_identity
        )
        flavors = tuple(
            catalog_flavor(
                candidate.flavor_revision,
                name=node.authoring.coordinate.name,
                axis=FlavorAxis.IMPLEMENTATION_LANGUAGE_ECOSYSTEM,
                value=candidate.value,
            )
            for node in plan.nodes
            for candidate in node.flavor_candidates
            if candidate.status is CandidateStatus.SELECTED
        )
        ordered = _ordered_selected_flavors(authoring, flavors, authority)
        self.assertEqual(len(ordered), 1)
        self.assertEqual(ordered[0].flavor.definition.coordinate.name, "invoice-cli")
