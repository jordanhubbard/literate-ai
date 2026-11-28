"""Shared public renderer against real root-repair source composition.

Original nodes, bounded requests and fresh replacement workspaces are genuine
local fixtures. Native rejection records are symbolic; no native authority,
generated process or qualification is established.
"""

import unittest
from dataclasses import fields, replace
from unittest import mock

from literate_ai.adapters import candidate_repair
from literate_ai.application import native_root_run as live
from literate_ai.application.native_root_repair_prompt import (
    render_native_root_repair_prompt,
)
from literate_ai.contracts.executable_components.context import (
    deterministic_token_estimate,
)
from literate_ai.contracts.native_root_continuation import NATIVE_ROOT_REPAIR_MESSAGE
from literate_ai.contracts.standard_lifecycle_membership import StandardNodeFailurePhase
from tests.critical import test_native_root_candidate_repair_port as fixture


class NativeRootRepairPromptTests(unittest.TestCase):
    setUp = fixture.NativeRootCandidateRepairPortTests.setUp
    owner = fixture.NativeRootCandidateRepairPortTests.owner
    binding = fixture.NativeRootCandidateRepairPortTests.binding
    native_failure = fixture.NativeRootCandidateRepairPortTests.native_failure
    build_failure = fixture.NativeRootCandidateRepairPortTests.build_failure
    attempt = fixture.NativeRootCandidateRepairPortTests.attempt
    prepare = fixture.NativeRootCandidateRepairPortTests.prepare

    def test_two_actual_replacements_always_render_from_original_public_prompt(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic1, rejection1 = self.native_failure(run)
            middle, incoming = self.prepare(
                owner, run, (first,), diagnostic1, rejection1
            )
            second, diagnostic2, rejection2 = self.native_failure(
                run, middle, (first,), incoming
            )
            final, _ = self.prepare(
                owner, run, (first, second), diagnostic2, rejection2
            )
            for prepared, prefix, diagnostic in (
                (middle, (first,), diagnostic1),
                (final, (first, second), diagnostic2),
            ):
                request, prompt = render_native_root_repair_prompt(
                    self.original.request, prefix, diagnostic
                )
                self.assertEqual(prepared.request.request, request)
                self.assertEqual(prepared.request.prompt, prompt)
                self.assertTrue(prompt.startswith(self.original.request.prompt))
                self.assertEqual(
                    prompt.count(b"## Bounded root candidate-repair evidence"), 1
                )
            self.assertNotEqual(
                middle.request.request.identity, final.request.request.identity
            )
            self.assertNotEqual(
                middle.workspace.allocation_identity,
                final.workspace.allocation_identity,
            )
            self.assertNotIn(diagnostic1.identity.uri.encode(), final.request.prompt)

    def test_native_feedback_is_fixed_and_every_old_bounded_field_is_preserved(self):
        with self.owner() as owner:
            run = self.binding(owner)
            first, diagnostic, _rejection = self.native_failure(run)
            request, prompt = render_native_root_repair_prompt(
                self.original.request, (first,), diagnostic
            )
        original = self.original.request.request
        self.assertIn(NATIVE_ROOT_REPAIR_MESSAGE.encode(), prompt)
        self.assertNotIn(self.canary.encode(), prompt)
        self.assertNotIn(b"native-execution-0", prompt)
        self.assertNotIn(b"source-tree-0", prompt)
        self.assertNotEqual(request.identity, original.identity)
        for field in fields(original):
            if field.name != "prompt_identity":
                self.assertIs(
                    getattr(request, field.name), getattr(original, field.name)
                )

    def test_build_and_test_diagnostics_keep_exact_original_runtime_framing(self):
        for phase, code, text in (
            (
                StandardNodeFailurePhase.BUILD,
                "builder.generated-source-rejected",
                "generated build failed",
            ),
            (
                StandardNodeFailurePhase.TEST,
                "generated-test.failed",
                "generated tests failed",
            ),
        ):
            with (
                self.subTest(phase=phase),
                self.owner() as owner,
                live.activate_native_root_run(owner),
            ):
                run = self.binding(owner)
                diagnostic = replace(
                    self.build_failure(), phase=phase, code=code, sanitized_text=text
                )
                first = self.attempt(
                    run,
                    self.original,
                    (),
                    None,
                    "node-rejected",
                    diagnostic.failure_evidence_identity,
                    diagnostic.identity,
                )
                prepared, _ = self.prepare(owner, run, (first,), diagnostic)
                # This is the original production wire framing, compared through
                # real adapter checks/allocation, not only helper self-consistency.
                expected = (
                    self.original.request.prompt
                    + (
                        "\n\n## Bounded root candidate-repair evidence\n"
                        f"Failure: {text}\n"
                        f"Diagnostic identity: {diagnostic.identity.uri}\n"
                        "Predecessor root candidate attempt identities:\n"
                        f"- {first.identity.uri}\n"
                        "Produce a complete fresh replacement; do not reuse prior "
                        "candidate files.\n"
                    ).encode()
                )
                self.assertEqual(prepared.request.prompt, expected)

    def test_actual_runtime_original_byte_cap_still_refuses_before_allocation(self):
        fixture.NativeRootCandidateRepairPortTests.test_bounded_feedback_cannot_expand_original_prompt_budget(
            self
        )

    def test_actual_runtime_total_prompt_token_cap_still_counts_old_framing(self):
        fixture.NativeRootCandidateRepairPortTests.test_full_original_prompt_framing_counts_against_retained_token_cap(
            self
        )

    def test_original_context_plus_suffix_token_cap_refuses_before_allocation(self):
        old = self.original.request.request
        tokens = max(
            old.context_manifest.estimated_tokens,
            deterministic_token_estimate(len(self.original.request.prompt)),
        )
        budget = replace(old.budget, max_estimated_tokens=tokens)
        decision = replace(old.budget_decision, budget_identity=budget.identity)
        request = replace(
            old,
            budget=budget,
            budget_decision=decision,
            complexity_decision_identity=decision.identity,
        )
        self.original = replace(
            self.original, request=replace(self.original.request, request=request)
        )
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch.object(
                candidate_repair.FilesystemComponentWorkspaceAllocator, "allocate"
            ) as allocate:
                with self.assertRaisesRegex(ValueError, "original prompt budget"):
                    self.prepare(owner, run, (first,), diagnostic, rejection)
            allocate.assert_not_called()

    def test_frozen_ordinary_v2_does_not_select_new_root_renderer(self):
        with mock.patch.object(
            candidate_repair,
            "render_native_root_repair_prompt",
            side_effect=AssertionError("ordinary v2 selected root renderer"),
        ) as render:
            prepared = self.adapter.prepare_repair(
                self.original, self.build_failure(), (fixture.ci("legacy-predecessor"),)
            )
        render.assert_not_called()
        self.assertIn(b"## Bounded candidate-repair evidence", prepared.request.prompt)
        self.assertNotIn(
            b"## Bounded root candidate-repair evidence", prepared.request.prompt
        )
        self.assertIs(
            prepared.request.request.budget_decision,
            self.original.request.request.budget_decision,
        )

    def test_tampered_original_prompt_and_incomplete_prefix_refuse_as_data(self):
        with self.owner() as owner:
            run = self.binding(owner)
            first, diagnostic, _ = self.native_failure(run)
            bad = replace(
                self.original.request, prompt=b"changed original public prompt"
            )
            with self.assertRaisesRegex(ValueError, "bounded identity"):
                render_native_root_repair_prompt(bad, (first,), diagnostic)
            for prefix in (
                (),
                (
                    replace(
                        first,
                        ordinal=1,
                        predecessor_root_attempt_identities=(
                            fixture.ci("hidden-original"),
                        ),
                        incoming_request_kind="native-root-repair",
                        incoming_request_identity=fixture.ci("foreign-request"),
                    ),
                ),
            ):
                with self.assertRaises(ValueError):
                    render_native_root_repair_prompt(
                        self.original.request, prefix, diagnostic
                    )
