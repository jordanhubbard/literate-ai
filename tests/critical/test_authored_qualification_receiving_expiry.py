"""Original read-scope retirement during a review cannot complete a live check."""

import unittest

from literate_ai.adapters import authored_qualification_receiving as receiving
from tests.critical import test_authored_qualification_receiving as fixture


class AuthoredReceivingExpiryTests(unittest.TestCase):
    setUpClass = classmethod(
        fixture.AuthoredQualificationReceivingTests.setUpClass.__func__
    )
    setUp = fixture.AuthoredQualificationReceivingTests.setUp
    open = fixture.AuthoredQualificationReceivingTests.open

    def test_callback_retirement_refuses_the_original_inflight_check(self):
        state = {"close": None, "retired": False}

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            close = state["close"]
            if close is not None:
                state["close"] = None
                close()
                state["retired"] = True
            return self.provider.review_identity

        manager = self.open(reviewer=reviewer)
        current = manager.__enter__()
        try:
            state["close"] = lambda: manager.__exit__(None, None, None)
            # Require refusal by this in-flight operation, not only a later
            # registry lookup after the original context has already retired.
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)
            self.assertTrue(state["retired"])
            self.assertNotIn(id(current), receiving._ISSUED_CHECKS)
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)
        finally:
            manager.__exit__(None, None, None)

    def test_retirement_then_callback_failure_preserves_primary_exception(self):
        state = {"close": None}
        failure = RuntimeError("original callback failure after retirement")

        def reviewer(root, *, synchronize_source_intelligence):
            self.assertFalse(synchronize_source_intelligence)
            close = state["close"]
            if close is not None:
                state["close"] = None
                close()
                raise failure
            return self.provider.review_identity

        manager = self.open(reviewer=reviewer)
        current = manager.__enter__()
        try:
            state["close"] = lambda: manager.__exit__(None, None, None)
            with self.assertRaises(RuntimeError) as observed:
                receiving.require_reviewed_authored_qualification_inputs(current)
            self.assertIs(observed.exception, failure)
            self.assertNotIn(id(current), receiving._ISSUED_CHECKS)
            with self.assertRaisesRegex(ValueError, "expired"):
                receiving.require_reviewed_authored_qualification_inputs(current)
        finally:
            manager.__exit__(None, None, None)
