"""Real compiler/probe/binding facts, with explicit fixture provider admission.

The owned Cargo launcher is copied and made writable before measurement. This
does not execute the fixture workspace or qualify a model, SDK or admission.
"""

import copy
import os
import pickle
import shutil
import stat
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_tool_completion import (
    _capture_authored_consumer_tools,
)
from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_retained_cargo_retirement import (
    authored_retirement_fixture,
)


def _replace_owned_launcher(path: Path, marker: bytes) -> None:
    # Linux can retain an executable's write exclusion after a completed probe.
    # Replace only this fixture's selected pathname, preserving the changed bytes
    # for the production completion guard to reject after every real probe.
    replacement = path.with_name(path.name + ".changed")
    with replacement.open("xb") as stream:
        stream.write(path.read_bytes() + marker)
    replacement.chmod(stat.S_IMODE(path.stat().st_mode))
    replacement.replace(path)


class AuthoredToolCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory(prefix="atc-") as temporary:
            base = Path(temporary).resolve()
            original = joins.AuthoredRetainedCargoInputsTests.cargo
            path = base / Path(original.command[0]).name
            shutil.copy2(original.command[0], path)
            path.chmod(stat.S_IMODE(path.stat().st_mode) | stat.S_IWUSR)
            measured = discover_cargo_toolchain(pinned_command=str(path))
            receiving = {}
            with authored_retirement_fixture(
                self,
                receiving_state=receiving,
                consumer_cargo=measured,
            ) as (materialized, _relative, _reference, _retired, _before):
                home = base / "home"
                home.mkdir()
                environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
                inputs = read_authored_retained_cargo_execution_inputs(
                    materialized,
                    environment=environment,
                )
                cargo = LocalComponentToolBinding.from_observed_toolchain(measured)
                rustc = LocalComponentToolBinding.from_observed_toolchain(
                    materialized.current.rustc
                )
                state = {"armed": False, "changed": False}

                def gate_guard():
                    measured.require_unchanged()
                    if state["armed"]:
                        _replace_owned_launcher(path, b"preserved late gate callback")
                        state["armed"] = False
                        state["changed"] = True

                gate = LocalComponentToolBinding.from_observed_toolchain(
                    measured, guard=gate_guard
                )
                arguments = dict(
                    cargo=cargo,
                    rustc=rustc,
                    gate_tools={"fixture-gate": gate},
                    environment=environment,
                    deadline=time.monotonic() + 900,
                )
                yield inputs, arguments, receiving["close"], path, state

    def test_after_close_original_facts_and_full_probes_survive_without_expired_inputs(
        self,
    ):
        with self.fixture() as (inputs, args, close, _path, _state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()
            with self.assertRaises(ValueError):
                inputs.current_identity(environment=args["environment"])
            completion.refresh_current()
            trap = AssertionError("raw tool facts invoked probes or expired owner")
            with (
                patch.object(
                    CurrentAuthoredRetainedCargoInputs,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch("subprocess.run", side_effect=trap),
                patch("subprocess.Popen", side_effect=trap),
            ):
                completion.require_original_files()
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(TypeError):
                        operation(completion)

    def test_owned_original_cargo_bytes_refuse_after_close_and_remain_changed(self):
        with self.fixture() as (inputs, args, close, path, _state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()
            _replace_owned_launcher(path, b"preserved direct launcher drift")
            changed = path.read_bytes()
            with patch("subprocess.Popen", side_effect=AssertionError("raw probe")):
                with self.assertRaises(BuildError):
                    completion.require_original_files()
            self.assertEqual(path.read_bytes(), changed)

    def test_last_independent_gate_guard_cannot_mutate_an_earlier_compiler_launcher(
        self,
    ):
        with self.fixture() as (inputs, args, close, path, state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()
            before = path.stat().st_size
            state["armed"] = True
            with self.assertRaises(BuildError):
                completion.refresh_current()
            self.assertTrue(state["changed"])
            self.assertGreater(path.stat().st_size, before)
            self.assertTrue(path.read_bytes().endswith(b"preserved late gate callback"))

    def test_original_binding_environment_cannot_be_replaced_after_close(self):
        with self.fixture() as (inputs, args, close, _path, _state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()
            # Simulate a hostile in-process callback mutating a frozen original.
            changed = (("LITAI_COMPLETION_TEST", "changed"),)
            object.__setattr__(
                args["gate_tools"]["fixture-gate"], "environment", changed
            )
            with self.assertRaisesRegex(ValueError, "original-tool-binding-changed"):
                completion.require_original_files()
            self.assertEqual(args["gate_tools"]["fixture-gate"].environment, changed)

    def test_original_absolute_deadline_is_not_reset_for_refresh(self):
        with self.fixture() as (inputs, args, close, _path, _state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()
            with (
                patch("time.monotonic", return_value=args["deadline"] + 1),
                patch("subprocess.Popen", side_effect=AssertionError("expired probe")),
            ):
                with self.assertRaisesRegex(ValueError, "completion-deadline"):
                    completion.refresh_current()
            self.assertEqual(completion._deadline, args["deadline"])

    def test_expired_original_inputs_cannot_mint_a_new_expected_tool_baseline(self):
        with self.fixture() as (inputs, args, close, _path, _state):
            close()
            with self.assertRaises(ValueError):
                _capture_authored_consumer_tools(inputs, **args)

    def test_replaced_original_authority_guard_refuses_without_invoking_replacement(
        self,
    ):
        with self.fixture() as (inputs, args, close, _path, _state):
            completion = _capture_authored_consumer_tools(inputs, **args)
            close()

            class Replacement:
                calls = 0

                def __eq__(self, other):
                    return True

                def __call__(self):
                    self.calls += 1

            replacement = Replacement()
            gate = args["gate_tools"]["fixture-gate"]
            object.__setattr__(gate, "_authority_guard", replacement)
            with patch(
                "subprocess.Popen", side_effect=AssertionError("swapped guard probe")
            ):
                with self.assertRaisesRegex(
                    ValueError, "original-tool-binding-changed"
                ):
                    completion.refresh_current()
            self.assertEqual(replacement.calls, 0)
            self.assertIs(gate._authority_guard, replacement)
