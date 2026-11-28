"""Pure historical-marker invalidation; no fresh review or release claim."""

import unittest

from literate_ai.application.project_authority import (
    AUTHORITY_REVIEW_PLACEHOLDER,
    invalidate_authority_review,
)


class AuthorityInvalidationTests(unittest.TestCase):
    def test_expires_marker_and_preserves_body_bytes(self):
        marker = b"<!-- literate-ai:authority-reviewed sha256:" + b"a" * 64 + b" -->"
        before = b"# Original\r\n" + marker + b"\r\nKeep custom prose.\r\n"
        after = invalidate_authority_review(before)
        self.assertEqual(
            after,
            b"# Original\r\n"
            + AUTHORITY_REVIEW_PLACEHOLDER.encode()
            + b"\r\nKeep custom prose.\r\n",
        )
        self.assertIn(marker, before)
        self.assertNotIn(b"authority-reviewed", after)

    def test_pending_or_absent_marker_is_unchanged(self):
        for before in (b"# Local prose\n", AUTHORITY_REVIEW_PLACEHOLDER.encode()):
            self.assertEqual(invalidate_authority_review(before), before)

    def test_duplicate_markers_refuse_without_selecting_one(self):
        marker = b"<!-- literate-ai:authority-reviewed sha256:" + b"b" * 64 + b" -->"
        with self.assertRaises(ValueError):
            invalidate_authority_review(marker + b"\n" + marker)

    def test_nonbyte_inputs_refuse(self):
        with self.assertRaises(TypeError):
            invalidate_authority_review("untyped input")
