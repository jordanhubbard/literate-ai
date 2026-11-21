"""SDK grants follow the operator's current revocation file across reads."""

import json
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.native_sdk_revocation_file import SdkRevocationFile
from literate_ai.security import AuthorizationRevocationSet


class AuthoredSdkRevocationTests(unittest.TestCase):
    def test_replacement_is_visible_and_rollback_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / "revocations.json"
            empty = AuthorizationRevocationSet()
            path.write_text(json.dumps(empty.to_dict()))
            read = SdkRevocationFile(path)
            self.assertEqual(read(), empty)
            revoked = empty.revoke(
                "sdk-fixture-grant", actor="operator", reason="withdrawn"
            )
            replacement = root / "next.json"
            replacement.write_text(json.dumps(revoked.to_dict()))
            replacement.replace(path)
            self.assertEqual(read(), revoked)
            self.assertEqual(SdkRevocationFile(path)(), revoked)
            path.write_text(json.dumps(empty.to_dict()))
            with self.assertRaisesRegex(ValueError, "revocation disappeared"):
                read()
