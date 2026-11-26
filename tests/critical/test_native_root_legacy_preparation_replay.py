"""Closed ordinary v2 lineage preparation, with actual CAS/pure current plans.

Collect the accompanying preparation replay B patch before running these controls.
Node/source observations are symbolic; stage/native acceptance remains separate.
"""

import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.native_root_preparation_replay import (
    NativeRootPreparationReplayError,
)
from literate_ai.application.candidate_repair_prompt import (
    render_candidate_repair_prompt,
)
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationRequest,
)
from literate_ai.contracts.executable_components import (
    CandidateAttemptChain,
    CandidateAttemptChainDisposition,
    CandidateRepairRequest,
)
from literate_ai.contracts.native_root_continuation import NativeRootContinuationLedger
from tests.critical import test_native_root_preparation_replay as fixture


class NativeRootLegacyPreparationReplayTests(unittest.TestCase):
    project = fixture.NativeRootPreparationReplayTests.project
    record = fixture.NativeRootPreparationReplayTests.record
    put_json = fixture.NativeRootPreparationReplayTests.put_json
    put = fixture.NativeRootPreparationReplayTests.put
    locator = fixture.NativeRootPreparationReplayTests.locator
    allocation = fixture.NativeRootPreparationReplayTests.allocation
    reader = fixture.NativeRootPreparationReplayTests.reader
    verify = fixture.NativeRootPreparationReplayTests.verify

    def setUp(self):
        fixture.NativeRootPreparationReplayTests.setUp(self)
        legacy, incoming, preparations = [], [], []
        for index in range(3):
            if index == 0:
                request, prompt = (
                    self.current.original.request,
                    self.current.original.prompt,
                )
                repair = None
            else:
                request, prompt = render_candidate_repair_prompt(
                    self.current.original,
                    self.diagnostics[index - 1],
                    tuple(item.identity for item in legacy),
                )
                repair = CandidateRepairRequest(
                    self.run.root_revision,
                    index,
                    self.run.original_recipe_identity,
                    tuple(item.identity for item in legacy),
                    self.diagnostics[index - 1].identity,
                    request.identity,
                    self.allocation(index),
                )
                self.put(repair)
            item = replace(
                self.fixture.legacy0,
                component_revision=self.run.root_revision,
                attempt_index=index,
                generation_request_identity=request.identity,
                generation_response_identity=self.attempts[
                    index
                ].source_output_identity,
                lifecycle_result_identity=self.attempts[
                    index
                ].node_lifecycle_result_identity,
                workspace_allocation_identity=self.allocation(index),
                predecessor_attempt_identities=tuple(item.identity for item in legacy),
                diagnostic=self.diagnostics[index],
                repair_request=repair,
            )
            legacy.append(item)
            incoming.append(repair)
            self.put(request)
            self.record(prompt)
            preparations.append((request, prompt, self.preparations[index][2]))
        chain = CandidateAttemptChain(
            self.run.root_revision,
            tuple(legacy),
            CandidateAttemptChainDisposition.EXHAUSTED,
        )
        self.put(chain)
        roots = []
        for index, prior in enumerate(self.attempts):
            roots.append(
                replace(
                    prior,
                    predecessor_root_attempt_identities=tuple(
                        item.identity for item in roots
                    ),
                    incoming_request_kind="initial"
                    if index == 0
                    else "legacy-node-repair",
                    incoming_request_identity=None
                    if index == 0
                    else incoming[index].identity,
                    bounded_generation_request_identity=preparations[index][0].identity,
                    legacy_node_chain_identity=chain.identity,
                    legacy_node_attempt_index=index,
                )
            )
        self.attempts, self.preparations = roots, preparations
        self.ledger = NativeRootContinuationLedger(
            self.run.identity, tuple(roots), (chain.identity,), "exhausted", None
        )

    def test_two_legacy_repairs_use_same_original_base_and_preserve_held_fields(self):
        verified = self.verify()
        self.assertEqual(
            tuple((item.request, item.prompt, item.workspace) for item in verified),
            tuple(self.preparations),
        )
        for item in verified:
            self.assertEqual(
                item.request.context_manifest,
                self.current.original.request.context_manifest,
            )
            self.assertEqual(item.request.budget, self.current.original.request.budget)
            self.assertEqual(
                item.request.budget_decision,
                self.current.original.request.budget_decision,
            )
        self.assertEqual(
            verified[2].prompt.count(b"## Bounded candidate-repair evidence"), 1
        )

    def test_missing_or_changed_legacy_public_prompt_refuses(self):
        identity = self.preparations[1][0].prompt_identity
        del self.records[identity]
        with self.assertRaises((ValueError, fixture.QualificationCaptureError)):
            self.verify()

    def test_nested_previous_repair_prompt_cannot_be_substituted(self):
        previous = self.preparations[1]
        with mock.patch(
            "literate_ai.adapters.native_root_preparation_replay.render_candidate_repair_prompt",
            side_effect=lambda _base, diagnostic, predecessors: (
                render_candidate_repair_prompt(
                    PreparedComponentGenerationRequest(previous[0], previous[1]),
                    diagnostic,
                    predecessors,
                )
            ),
        ):
            with self.assertRaises(NativeRootPreparationReplayError):
                self.verify()
