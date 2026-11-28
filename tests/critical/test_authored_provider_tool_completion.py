"""Actual provider factory observations with explicit admission/platform fixtures."""

import copy
import pickle
import time
import unittest
from unittest.mock import patch

from literate_ai.adapters import authored_provider_tool_completion as tools_module
from literate_ai.adapters import authored_qualification_projection as projection
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.builders import BuildError
from literate_ai.adapters.builders.python import PythonToolchain
from literate_ai.adapters.standard_project import (
    ProjectedStandardToolchainClosure,
    _project_locked_standard_toolchain_closure_session,
)
from tests.critical import test_authored_qualification_projection as fixtures
from tests.smoke import test_python_original_files as python_fixtures


class AuthoredProviderToolCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AuthoredQualificationProjectionTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.current = self.fixture.current
        self.python = python_fixtures.PythonOriginalFilesTests("runTest")
        self.addCleanup(self.python.doCleanups)
        self.python.setUp()
        self.enterContext(
            patch(
                "literate_ai.adapters.standard_project._host_platform_target",
                return_value="macos",
            )
        )

        def original_factory(*args, **kwargs):
            return _project_locked_standard_toolchain_closure_session(
                *args,
                **kwargs,
                toolchain_discoverer=lambda *_: self.python.selected,
            )

        self.enterContext(
            patch.object(
                projection,
                "_project_locked_standard_toolchain_closure_session",
                side_effect=original_factory,
            )
        )

    def capture(self):
        return projection._open_current_authored_qualification_projection_session(
            self.current
        )

    def test_actual_factory_objects_refresh_after_close_without_reviving_public_owner(
        self,
    ):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            original = session.completion._tool_completion
            self.assertIs(original._closure, session.completion._closure)
            self.assertTrue(original._tools)
            for _role, tool, original_type, _fields in original._tools:
                self.assertIs(tool, self.python.selected)
                self.assertIs(original_type, PythonToolchain)
        with self.assertRaisesRegex(ValueError, "projection_owner_expired"):
            session.projection.require_unchanged()
        session.completion.refresh_current(deadline=deadline)
        trap = AssertionError("raw original provider facts invoked a callback")
        with (
            patch.object(
                ProjectedStandardToolchainClosure, "require_unchanged", side_effect=trap
            ),
            patch.object(PythonToolchain, "require_unchanged", side_effect=trap),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            session.completion.require_original_files()
        for value in (original, session):
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(
                    type=type(value).__name__, operation=operation.__name__
                ):
                    with self.assertRaises(TypeError):
                        operation(value)

    def test_last_actual_current_callback_runtime_mutation_refuses_and_is_preserved(
        self,
    ):
        with self.capture() as session:
            pass
        changed = self.python.runtime.read_bytes() + b"preserve final provider runtime"
        actual = CurrentAuthoredQualificationPlan.require_unchanged
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is self.current:
                calls.append(owner)
                if len(calls) == 2:
                    self.python.runtime.write_bytes(changed)
            return result

        with patch.object(
            CurrentAuthoredQualificationPlan, "require_unchanged", new=late
        ):
            with self.assertRaisesRegex(BuildError, "runtime bytes changed"):
                session.completion.refresh_current(deadline=time.monotonic() + 900)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.python.runtime.read_bytes(), changed)

    def test_original_measured_tool_fields_cannot_be_replaced_after_close(self):
        with self.capture() as session:
            pass
        changed = self.python.selected.version + " preserve changed measured metadata"
        object.__setattr__(self.python.selected, "version", changed)
        with self.assertRaisesRegex(ValueError, "original-provider-tool-changed"):
            session.completion.require_original_files()
        self.assertEqual(self.python.selected.version, changed)

    def test_equal_claiming_replacement_authority_guard_is_not_invoked(self):
        with self.capture() as session:
            pass
        authority = session.completion._closure.toolchain_authorities[0]
        calls = []

        class Replacement:
            def __eq__(self, other):
                return True

            def __call__(self):
                calls.append(True)

        replacement = Replacement()
        object.__setattr__(authority, "_guard", replacement)
        with self.assertRaisesRegex(
            ValueError, "(original-provider-guard|projection-tool-guard)-changed"
        ):
            session.completion.require_original_files()
        self.assertEqual(calls, [])
        self.assertIs(authority._guard, replacement)

    def test_original_deadline_refuses_before_and_after_actual_closure_refresh(self):
        with self.capture() as session:
            pass
        original = session.completion._tool_completion
        for deadline in (float("nan"), float("inf"), True, 0, time.monotonic() - 1):
            with self.subTest(deadline=deadline):
                with patch.object(
                    ProjectedStandardToolchainClosure, "require_unchanged"
                ) as refresh:
                    with self.assertRaisesRegex(ValueError, "provider-tool-deadline"):
                        original.refresh_current(deadline=deadline)
                refresh.assert_not_called()
        actual = ProjectedStandardToolchainClosure.require_unchanged
        clock = [10.0]
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is original._closure:
                calls.append(owner)
                clock[0] = 12.0
            return result

        with (
            patch.object(
                ProjectedStandardToolchainClosure, "require_unchanged", new=late
            ),
            patch.object(tools_module.time, "monotonic", side_effect=lambda: clock[0]),
        ):
            with self.assertRaisesRegex(ValueError, "provider-tool-deadline-expired"):
                original.refresh_current(deadline=11.0)
        self.assertEqual(calls, [original._closure])
