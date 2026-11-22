"""Wide native filesystem identity retains live reservation custody."""

import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.native_sdk_workspace import native_sdk_build_workspace
from tests.critical.test_native_child_stat_identity import wide_stat_identifiers


class NativeSdkWorkspaceIdentityTests(unittest.TestCase):
    def test_wide_native_ids_do_not_break_reservation_backed_allocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            with wide_stat_identifiers():
                with native_sdk_build_workspace(parent) as workspace:
                    workspace.require_unchanged()
                    self.assertTrue(workspace.identity.uri.startswith("sha256:"))
                    # The reservation keeps raw OS values for live comparisons.
                    self.assertGreaterEqual(workspace._node[0], 1 << 63)
                    self.assertGreaterEqual(workspace._node[1], 1 << 127)
                with self.assertRaisesRegex(ValueError, "ended"):
                    workspace.require_unchanged()
