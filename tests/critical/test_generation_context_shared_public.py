"""Shared public-byte presentation retains all original authority checks."""

import unittest
from dataclasses import replace

from literate_ai.application.component_generation_context import (
    ComponentGenerationContextError,
    GenerationComplexityBudgetExceeded,
    prepare_component_generation_context,
)
from literate_ai.contracts._validation import ContractValidationError
from literate_ai.contracts.executable_components.context import (
    ContextAuthorityKind as Kind,
)
from literate_ai.contracts.executable_components.context import (
    ContextVisibility,
)
from tests.support.fixtures_test_component_generation_context import (
    _budget,
    _diamond_lock,
    _materialize,
    _named_plan,
)


class SharedPublicContextTests(unittest.TestCase):
    def setUp(self):
        plan, inputs = _materialize(_named_plan(_diamond_lock(), "invoice-cli"))
        self.direct = next(
            item
            for item in inputs
            if item.authority_kind is Kind.DIRECT_PUBLIC_INTERFACE
        )
        self.plan = replace(
            plan,
            generation_key=replace(
                plan.generation_key,
                exported_public_interface_identities=(self.direct.content_identity,),
            ),
        )
        self.local = replace(
            self.direct,
            authority_kind=Kind.LOCAL_PUBLIC_INTERFACE,
            source_component_revision=plan.component_revision,
            reason="the same bytes are also the selected local public interface",
        )
        self.inputs = (
            *(
                item
                for item in inputs
                if item.authority_kind is not Kind.LOCAL_PUBLIC_INTERFACE
            ),
            self.local,
        )

    def prepare(self, inputs=None, *, plan=None, budget=None):
        return prepare_component_generation_context(
            self.plan if plan is None else plan,
            framework_envelope=b"trusted framework envelope",
            authority_segments=self.inputs if inputs is None else inputs,
            budget=_budget() if budget is None else budget,
        )

    def test_shared_public_bytes_are_present_once_with_direct_visibility_and_quota(
        self,
    ):
        before = self.plan.to_dict()
        result = self.prepare()
        request = result.request
        matching = [
            item
            for item in request.context_manifest.segments
            if item.content_identity == self.direct.content_identity
        ]
        self.assertEqual(len(matching), 1)
        self.assertIs(matching[0].authority_kind, Kind.DIRECT_PUBLIC_INTERFACE)
        self.assertIs(matching[0].visibility, ContextVisibility.DIRECT_PUBLIC_INTERFACE)
        self.assertEqual(
            matching[0].source_component_revision, self.direct.source_component_revision
        )
        self.assertEqual(result.prompt.count(self.direct.content), 1)
        self.assertEqual(request.component_generation_plan_identity, self.plan.identity)
        self.assertEqual(
            request.generation_key_identity, self.plan.generation_key.identity
        )
        self.assertIn(
            self.direct.content_identity,
            self.plan.generation_key.exported_public_interface_identities,
        )
        self.assertIn(
            self.direct.content_identity,
            self.plan.generation_key.direct_public_interface_identities,
        )
        direct_bytes = sum(
            len(item.content)
            for item in self.inputs
            if item.authority_kind is Kind.DIRECT_PUBLIC_INTERFACE
        )
        self.assertEqual(request.budget_decision.direct_interface_bytes, direct_bytes)
        self.assertEqual(
            request.budget_decision.dependency_fan_in,
            len({edge.provider_revision for edge in self.plan.direct_generation_edges}),
        )
        reordered = self.prepare(tuple(reversed(self.inputs)))
        self.assertEqual(reordered.request, request)
        self.assertEqual(reordered.prompt, result.prompt)
        with self.assertRaises(GenerationComplexityBudgetExceeded) as caught:
            self.prepare(budget=_budget(max_direct_interface_bytes=direct_bytes - 1))
        self.assertIn("direct_interface_bytes", caught.exception.decision.violations)
        self.assertEqual(self.plan.to_dict(), before)

    def test_collapsed_local_role_still_requires_complete_authentic_input(self):
        without_local = tuple(item for item in self.inputs if item is not self.local)
        cases = (
            (without_local, "generation_context.authority_incomplete"),
            (
                (
                    *without_local,
                    replace(self.local, content=self.local.content + b"drift"),
                ),
                "generation_context.content_drift",
            ),
            (
                (
                    *without_local,
                    replace(
                        self.local,
                        source_component_revision=self.direct.source_component_revision,
                    ),
                ),
                "generation_context.source_component_mismatch",
            ),
            ((*self.inputs, self.local), "generation_context.authority_duplicate"),
            (
                (
                    *self.inputs,
                    replace(self.direct, authority_kind=Kind.ACCEPTANCE_ORACLE),
                ),
                "generation_context.authority_forbidden",
            ),
        )
        for inputs, code in cases:
            with (
                self.subTest(code=code),
                self.assertRaises(ComponentGenerationContextError) as caught,
            ):
                self.prepare(inputs)
            self.assertEqual(caught.exception.code, code)

    def test_equal_bytes_in_unrelated_authority_roles_still_refuse(self):
        plan = replace(
            self.plan,
            generation_key=replace(
                self.plan.generation_key,
                skill_identities=(self.direct.content_identity,),
            ),
        )
        inputs = (
            *(
                item
                for item in self.inputs
                if item.authority_kind is not Kind.LOCAL_SKILL
            ),
            replace(self.local, authority_kind=Kind.LOCAL_SKILL),
        )
        with self.assertRaisesRegex(
            ContractValidationError, "must not repeat content identities"
        ):
            self.prepare(inputs, plan=plan)
