"""Real interpreter files and a separately executed baseline; no provider grant."""

from __future__ import annotations

import copy
import os
import pickle
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_python_interpreter as observer
from literate_ai.adapters.builders import python as builder
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


class RetainedPythonInterpreterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # An actual native probe independently supplies the expected identity.
        # No such process is permitted inside the read-only observation below.
        cls.baseline = builder.discover_python_toolchain(pinned_command=sys.executable)

    def observing(self, *, command=None, identity=None, **limits):
        return observer.observed_retained_python_interpreter(
            self.baseline.command if command is None else command,
            expected_identity=ContentIdentity.parse_uri(
                self.baseline.identity if identity is None else identity
            ),
            maximum_file_bytes=limits.get("maximum_file_bytes", 256 * 1024**2),
            maximum_metadata_bytes=limits.get("maximum_metadata_bytes", 1024**3),
        )

    def no_processes(self):
        return mock.patch.object(
            builder,
            "_run_bounded_process",
            side_effect=AssertionError("read-only interpreter started a native tool"),
        )

    def test_actual_runtime_matches_independent_native_probe_without_processes(self):
        runtime = Path(sys.executable).resolve()
        before = runtime.stat()
        with (
            self.no_processes(),
            mock.patch(
                "subprocess.Popen",
                side_effect=AssertionError("unexpected native child"),
            ),
        ):
            with self.observing() as current:
                self.assertEqual(current.identity, self.baseline.identity)
                self.assertEqual(current.command, self.baseline.command)
                for _ in range(3):
                    current.require_unchanged()
        after = runtime.stat()
        self.assertEqual(
            (before.st_mode, before.st_size, before.st_mtime_ns),
            (after.st_mode, after.st_size, after.st_mtime_ns),
        )

    def test_observation_cannot_copy_serialize_or_outlive_its_original_scope(self):
        with self.no_processes():
            with self.observing() as current:
                for copy_value in (copy.copy, copy.deepcopy, pickle.dumps):
                    with self.subTest(operation=copy_value.__name__):
                        with self.assertRaises(TypeError):
                            copy_value(current)
            with mock.patch.object(
                Path, "open", side_effect=AssertionError("expired native file read")
            ):
                with self.assertRaisesRegex(ValueError, "observation-ended"):
                    current.require_unchanged()

    def test_private_callback_or_tool_replacement_cannot_bypass_original_registry(self):
        with self.no_processes():
            for name in ("_tool", "_check"):
                with self.subTest(field=name), self.observing() as current:
                    original = getattr(current, name)
                    try:
                        object.__setattr__(current, name, lambda *args: None)
                        with mock.patch.object(
                            Path,
                            "open",
                            side_effect=AssertionError("foreign owner read"),
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "original.*changed"
                            ):
                                current.require_unchanged()
                    finally:
                        object.__setattr__(current, name, original)

    def test_final_real_byte_reader_callback_cannot_replace_tool_fields(self):
        actual_read = PinnedInputClosure.require_unchanged
        with self.no_processes(), self.observing() as current:
            original = current._tool.identity
            reached = []

            def read_then_change(inputs):
                actual_read(inputs)
                reached.append(True)
                object.__setattr__(current._tool, "identity", "sha256:" + "0" * 64)

            try:
                with mock.patch.object(
                    PinnedInputClosure, "require_unchanged", read_then_change
                ):
                    with self.assertRaisesRegex(ValueError, "original.*changed"):
                        current.require_unchanged()
            finally:
                object.__setattr__(current._tool, "identity", original)
            self.assertEqual(reached, [True])

    def test_native_reentry_refuses_and_releases_its_check_slot(self):
        actual_read = PinnedInputClosure.require_unchanged
        with self.no_processes(), self.observing() as current:
            reached = []

            def reenter(inputs):
                actual_read(inputs)
                reached.append(True)
                current.require_unchanged()

            with mock.patch.object(PinnedInputClosure, "require_unchanged", reenter):
                with self.assertRaisesRegex(ValueError, "reentrant"):
                    current.require_unchanged()
            self.assertEqual(reached, [True])
            current.require_unchanged()

    def test_last_real_read_cannot_revoke_registration_or_replace_input_closure(self):
        actual_read = PinnedInputClosure.require_unchanged
        with self.no_processes():
            for target in ("registration", "inputs"):
                with self.subTest(target=target), self.observing() as current:
                    original_check = observer._OWNERS[current]
                    reached = []

                    def read_then_poison(
                        inputs, *, target=target, reached=reached, current=current
                    ):
                        actual_read(inputs)
                        reached.append((inputs, inputs._entries))
                        if target == "registration":
                            observer._OWNERS.pop(current)
                        else:
                            inputs._entries = {}

                    try:
                        with mock.patch.object(
                            PinnedInputClosure, "require_unchanged", read_then_poison
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "original.*changed"
                            ):
                                current.require_unchanged()
                    finally:
                        observer._OWNERS[current] = original_check
                        for inputs, entries in reached:
                            inputs._entries = entries
                    self.assertEqual(len(reached), 1)
                    current.require_unchanged()

    def test_exact_pin_and_native_read_limits_are_required(self):
        with self.no_processes():
            with self.assertRaisesRegex(ValueError, "identity-mismatch"):
                with self.observing(identity="sha256:" + "0" * 64):
                    self.fail("substituted identity admitted")
            with self.assertRaises(PinnedInputClosureError) as caught:
                with self.observing(maximum_file_bytes=1):
                    self.fail("oversized native executable admitted")
            self.assertEqual(caught.exception.code, "inputs.closure_file_size_limit")
            with mock.patch.object(
                observer,
                "_resolved_python_command",
                side_effect=AssertionError("invalid budget touched filesystem"),
            ):
                for limits in (
                    {"maximum_file_bytes": True},
                    {"maximum_metadata_bytes": 65536},
                    {"maximum_file_bytes": 256 * 1024**2 + 1},
                ):
                    with self.subTest(limits=limits):
                        with self.assertRaisesRegex(ValueError, "selection-invalid"):
                            with self.observing(**limits):
                                self.fail("invalid allowance admitted")

    @unittest.skipUnless(os.name == "posix", "actual POSIX command alias replacement")
    def test_same_byte_foreign_launcher_and_changed_alias_remain_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            alias, foreign = root / "python", root / "foreign-python"
            alias.symlink_to(Path(sys.executable).resolve())
            shutil.copy2(Path(sys.executable).resolve(), foreign)
            baseline = builder.discover_python_toolchain(pinned_command=str(alias))
            refused = []
            with self.no_processes():
                with self.assertRaisesRegex(ValueError, "nonrunning-interpreter"):
                    with self.observing(command=(str(foreign),)):
                        self.fail("different native launcher claimed this runtime")
                with self.assertRaises(ValueError):
                    with self.observing(
                        command=baseline.command, identity=baseline.identity
                    ) as current:
                        alias.unlink()
                        alias.symlink_to(foreign)
                        try:
                            current.require_unchanged()
                        except ValueError:
                            refused.append(True)
                            raise
            self.assertEqual(refused, [True])
            self.assertEqual(alias.readlink(), foreign)
