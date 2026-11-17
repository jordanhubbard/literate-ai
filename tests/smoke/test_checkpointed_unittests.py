"""Tests for per-test fail-fast repair checkpoints."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from literate_ai.test_checkpointing import run_unittest_suite
from scripts.run_checkpointed_unittests import run_suite


class CheckpointedUnittestTests(unittest.TestCase):
    def test_unknown_project_inputs_cannot_reuse_python_test_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            dependency = root / "input.txt"
            dependency.write_text("correct")
            fail_final = True

            class Cases(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(dependency.read_text(), "correct")

                def test_b(self):
                    self.assertFalse(fail_final)

            def attempt():
                return run_unittest_suite(
                    unittest.defaultTestLoader.loadTestsFromTestCase(Cases),
                    state_path=root / "checkpoint.json",
                    project_root=root,
                    stream=io.StringIO(),
                )

            self.assertEqual(attempt(), 1)
            fail_final = False
            dependency.write_text("broken")
            self.assertEqual(attempt(), 1)
            dependency.write_text("correct")
            self.assertEqual(attempt(), 0)

    def test_failure_resume_and_required_from_zero_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "python-tests.json"
            executions: list[str] = []
            failing = True

            class Cases(unittest.TestCase):
                def test_a(self) -> None:
                    executions.append("a")

                def test_b(self) -> None:
                    executions.append("b")
                    if failing:
                        self.fail("repair me")

            def suite() -> unittest.TestSuite:
                return unittest.defaultTestLoader.loadTestsFromTestCase(Cases)

            self.assertEqual(
                run_suite(suite(), state_path=state, stream=io.StringIO()), 1
            )
            self.assertEqual(executions, ["a", "b"])
            self.assertTrue(state.exists())

            failing = False
            executions.clear()
            self.assertEqual(
                run_suite(suite(), state_path=state, stream=io.StringIO()), 2
            )
            self.assertEqual(executions, ["b"])
            self.assertFalse(state.exists())

            executions.clear()
            self.assertEqual(
                run_suite(suite(), state_path=state, stream=io.StringIO()), 0
            )
            self.assertEqual(executions, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
