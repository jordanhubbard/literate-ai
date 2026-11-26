"""Independent live sequence review using symbolic closed root records only."""

import unittest
from dataclasses import replace

from literate_ai.application.native_root_candidate_sequence import (
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.contracts._validation import ContractValidationError
from tests.critical import test_native_root_candidate_sequence as fixture


class NativeRootSequenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.NativeRootCandidateSequenceTests()
        self.fixture.setUp()

    def test_authority_callback_cannot_replace_binding_after_initial_join(self):
        records = self.fixture.records
        with self.fixture.original_run() as owner:
            binding = replace(
                records.run,
                run_nonce=owner.deadline.run_nonce,
                original_deadline_identity=owner.deadline.identity,
            )
            expected_authority = binding.project_authority_identity
            calls = []

            def current():
                calls.append(True)
                if len(calls) == 1:
                    object.__setattr__(
                        binding,
                        "project_authority_identity",
                        fixture.ci("foreign-authority"),
                    )

            admitted = False
            try:
                with open_native_root_candidate_sequence(
                    owner,
                    binding,
                    project_authority_identity=expected_authority,
                    require_current=current,
                    qualified_dependencies=(records.dependency,),
                ):
                    admitted = True
            except (NativeRootRunError, ContractValidationError):
                pass
            self.assertTrue(calls)
            self.assertFalse(
                admitted, "callback replaced approved authority before its new seal"
            )
