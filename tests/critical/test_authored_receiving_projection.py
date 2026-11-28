"""Actual native Python projection/completion; declared platform remains a fixture.

Like the original projection cohort, the lock explicitly targets macOS and the
controller observes its actual Python tool. No native macOS, generated product,
archive admission or genuine SDK/consumer qualification is established here.
"""

import time
import unittest
from unittest.mock import patch

from literate_ai.adapters.authored_qualification_projection import (
    _open_current_authored_qualification_projection_session,
)
from tests.critical import test_authored_qualification_receiving as fixture


class AuthoredReceivingProjectionTests(unittest.TestCase):
    setUpClass = classmethod(
        fixture.AuthoredQualificationReceivingTests.setUpClass.__func__
    )
    setUp = fixture.AuthoredQualificationReceivingTests.setUp
    open = fixture.AuthoredQualificationReceivingTests.open

    def test_original_completion_uses_real_read_owner_and_actual_python_tools(self):
        with self.open() as current:
            with patch(
                "literate_ai.adapters.standard_project._host_platform_target",
                return_value="macos",
            ):
                with _open_current_authored_qualification_projection_session(
                    current
                ) as original:
                    projection = original.projection
                    completion = original.completion
                    projection.require_unchanged()
                    expected = {
                        p.component_revision
                        for p in current.plan.execution_plan.generation_plans
                    }
                    self.assertEqual(set(projection.recipes), expected)
                    self.assertEqual(set(projection.commands), expected)
                with self.assertRaisesRegex(ValueError, "projection_owner_expired"):
                    projection.require_unchanged()
                completion.require_original_files()
                deadline = time.monotonic() + 900
                completion.refresh_current(deadline=deadline)
                completion.require_original_files()
        with self.assertRaisesRegex(ValueError, "expired"):
            completion.require_original_files()
