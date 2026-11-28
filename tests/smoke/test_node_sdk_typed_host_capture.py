"""Original capture callback refusal with injected joins; no host/native success."""

import inspect
import os
import shutil
import unittest
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_authorization as authorization
from tests.smoke import test_node_sdk_verifier_issuance as issuance_fixture


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires original selected provider capture fixture",
)
class TypedHostCaptureSubstitutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        issuance_fixture.EnrolledVerifierIssuanceTests.setUpClass()

    def exercise(self, name):
        control = issuance_fixture.EnrolledVerifierIssuanceTests()
        self.addCleanup(control.doCleanups)
        c = control.bind()
        f = c.fixture
        original_owner = f.owner
        issue = authorization._ORIGINAL_ISSUE_HOST_VERIFIER_CAPTURE
        substitute = mock.Mock()
        patcher = mock.patch.object(authorization, name, substitute)
        changed = []

        def custody_owner():
            original_owner()
            frame = inspect.currentframe()
            try:
                while frame is not None:
                    if frame.f_code.co_filename == captures.__file__ and not changed:
                        changed.append(True)
                        patcher.start()
                    frame = frame.f_back
            finally:
                frame = None

        try:
            with mock.patch.object(f, "owner", custody_owner):
                with c.capture() as (handle, _ticket):
                    self.assertEqual(changed, [True])
                    with self.assertRaisesRegex(ValueError, "fixed SDK verifier"):
                        issue(control.ack, c.operation, f.ports, handle)
                    substitute.assert_not_called()
                    self.assertFalse(c.state._grants)
                    self.assertFalse(c.state._grant_payloads)
        finally:
            patcher.stop()

    def test_operation_helper_replaced_in_original_capture_callback_is_not_invoked(
        self,
    ):
        self.exercise("_require_host_verifier_operation")

    def test_issuer_helper_replaced_in_original_capture_callback_is_not_invoked(self):
        self.exercise("_issue_host_verifier_capture")
