"""Exact ordinary v2 repair bytes; no native qualification or eligibility claim."""

import hashlib
import unittest
from dataclasses import fields, replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.application.candidate_repair_prompt import (
    render_candidate_repair_prompt,
)
from literate_ai.contracts import ContentIdentity, HashAlgorithm
from tests.critical import test_native_root_candidate_repair_port as fixture


def _before(original, diagnostic, predecessors):
    """Frozen producer block before the shared-renderer extraction."""
    prompt = (
        original.prompt
        + (
            "\n\n## Bounded candidate-repair evidence\n"
            f"Failure: {diagnostic.sanitized_text}\n"
            f"Diagnostic identity: {diagnostic.identity.uri}\n"
            "Predecessor candidate attempt identities:\n"
            + "".join(f"- {identity.uri}\n" for identity in predecessors)
            + "Produce a complete fresh replacement; do not reuse prior candidate "
            "files.\n"
        ).encode()
    )
    return replace(
        original.request,
        prompt_identity=ContentIdentity(
            HashAlgorithm.SHA256, hashlib.sha256(prompt).hexdigest()
        ),
    ), prompt


class LegacyCandidateRepairPromptTests(unittest.TestCase):
    setUp = fixture.NativeRootCandidateRepairPortTests.setUp
    build_failure = fixture.NativeRootCandidateRepairPortTests.build_failure

    def test_before_after_request_and_public_prompt_bytes_are_identical(self):
        diagnostic = self.build_failure()
        for count in (1, 2):
            predecessors = tuple(
                ContentIdentity.parse_uri("sha256:" + str(index + 1) * 64)
                for index in range(count)
            )
            with self.subTest(count=count):
                expected = _before(self.original.request, diagnostic, predecessors)
                actual = render_candidate_repair_prompt(
                    self.original.request, diagnostic, predecessors
                )
                self.assertEqual(actual, expected)
                self.assertEqual(actual[0].to_dict(), expected[0].to_dict())
                self.assertEqual(actual[0].identity, expected[0].identity)

    def test_original_producer_keeps_eligibility_allocator_and_byte_result(self):
        diagnostic = self.build_failure()
        adapter = FilesystemStandardCandidateRepairAdapter({})
        predecessors = (ContentIdentity.parse_uri("sha256:" + "1" * 64),)
        expected, prompt = _before(self.original.request, diagnostic, predecessors)
        replacement = adapter.prepare_repair(self.original, diagnostic, predecessors)
        self.assertEqual(replacement.request.request, expected)
        self.assertEqual(replacement.request.prompt, prompt)
        self.assertNotEqual(
            replacement.workspace.allocation_identity,
            self.original.workspace.allocation_identity,
        )
        self.assertTrue(Path(replacement.workspace.locator).is_dir())
        with self.assertRaises(ValueError):
            adapter.prepare_repair(self.original, diagnostic, ())

    def test_renderer_preserves_every_original_field_except_prompt_identity(self):
        request, _prompt = render_candidate_repair_prompt(
            self.original.request,
            self.build_failure(),
            (ContentIdentity.parse_uri("sha256:" + "1" * 64),),
        )
        for member in fields(request):
            if member.name != "prompt_identity":
                self.assertEqual(
                    getattr(request, member.name),
                    getattr(self.original.request.request, member.name),
                )

    def test_pure_rendering_has_no_workspace_cwd_or_executable_access(self):
        with (
            mock.patch.object(Path, "cwd", side_effect=AssertionError("CWD access")),
            mock.patch.object(
                Path, "resolve", side_effect=AssertionError("path access")
            ),
        ):
            request, prompt = render_candidate_repair_prompt(
                self.original.request,
                self.build_failure(),
                (ContentIdentity.parse_uri("sha256:" + "1" * 64),),
            )
        self.assertNotEqual(request.identity, self.original.request.request.identity)
        self.assertTrue(prompt.startswith(self.original.request.prompt))
