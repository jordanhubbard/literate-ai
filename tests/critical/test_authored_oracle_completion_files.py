"""Original oracle files through actual authored project/lock readers.

The maintained authority fixture uses Python v1 oracles. Rust v2 loaded-file
scope controls are separate; no native, model or admission proof is claimed.
"""

import copy
import pickle
import unittest
from unittest.mock import patch

from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.adapters.authored_qualification_oracles import (
    AuthoredQualificationOracleError,
    CurrentAuthoredQualificationOracles,
)
from literate_ai.projects import PinnedInputClosureError
from tests.critical import test_authored_qualification_oracles as fixtures


class AuthoredOracleCompletionFilesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AuthoredQualificationOracleTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.current = self.fixture.read()

    def test_original_files_after_scope_close_need_no_authority_or_command_callback(
        self,
    ):
        with self.current._capture_current_session() as files:
            files.require_original_files()
        self.current.require_unchanged()
        trap = AssertionError("raw oracle files invoked a current authority or command")
        with (
            patch.object(
                CurrentAuthoredQualificationAuthority,
                "require_unchanged",
                side_effect=trap,
            ),
            patch.object(
                CurrentAuthoredQualificationOracles, "capture_current", side_effect=trap
            ),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            files.require_original_files()
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(TypeError):
                    operation(files)

    def test_changed_original_profile_bytes_refuse_and_are_preserved(self):
        with self.current._capture_current_session() as files:
            pass
        path = self.fixture.profile_path
        changed = path.read_bytes() + b"\n"
        path.write_bytes(changed)
        with self.assertRaises(PinnedInputClosureError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), changed)

    def test_changed_original_harness_bytes_refuse_and_are_preserved(self):
        with self.current._capture_current_session() as files:
            pass
        path = self.fixture.oracle_root / "harness.py"
        changed = path.read_bytes() + b"# preserved foreign change\n"
        path.write_bytes(changed)
        with self.assertRaises(PinnedInputClosureError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), changed)

    def test_mutated_original_decoded_private_result_refuses_without_rebinding(self):
        with self.current._capture_current_session() as files:
            pass
        oracle = self.current.bindings[0].oracle
        oracle.cases[0].expected_result["private"] = "changed after capture"
        with self.assertRaises(AuthoredQualificationOracleError) as refused:
            files.require_original_files()
        self.assertEqual(
            refused.exception.code, "qualification.authored.oracle_changed"
        )
        self.assertEqual(
            oracle.cases[0].expected_result["private"], "changed after capture"
        )
