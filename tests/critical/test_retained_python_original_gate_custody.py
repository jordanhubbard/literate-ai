"""Raw original method custody; actual converted source fixtures, UNRUN draft.

No native result/provider admission is modeled. The deliberate descriptors must
never execute, even before the first native gate or after a current-input callback.
"""

from types import MethodType
from unittest import TestCase, mock, skipUnless

from literate_ai.adapters import retained_python_original_gates as subject
from literate_ai.adapters.retained_python_wrapper import (
    observed_retained_python_wrapper,
)
from tests.critical import test_retained_python_original_gates as original_gates


class _ForeignDescriptor:
    def __init__(self, original, calls):
        self.original, self.calls = original, calls

    def __eq__(self, other):
        self.calls.append("foreign equality")
        return True

    def __get__(self, receiver, owner):
        self.calls.append(receiver)
        return (
            self.original if receiver is None else MethodType(self.original, receiver)
        )


@skipUnless(
    not getattr(
        original_gates.ActualOriginalPythonGatesTests, "__unittest_skip__", False
    ),
    "same original POSIX Make source fixture",
)
class OriginalPythonGateDescriptorCustodyTests(TestCase):
    # Reuse provisioning without inheriting/discovering the original native tests.
    setUpClass = classmethod(
        original_gates.ActualOriginalPythonGatesTests.setUpClass.__func__
    )
    setUp = original_gates.ActualOriginalPythonGatesTests.setUp
    interpreter = original_gates.ActualOriginalPythonGatesTests.interpreter
    run_original = original_gates.ActualOriginalPythonGatesTests.run_original

    def test_before_first_descriptor_getter_is_never_invoked_or_adopted_later(self):
        original = subject._OriginalPythonGateObserver.__dict__["require_current"]
        calls = []
        foreign = _ForeignDescriptor(original, calls)
        with (
            self.interpreter() as interpreter,
            observed_retained_python_wrapper(
                self.fx.reviewed, budget=self.fx.budget
            ) as wrapper,
            mock.patch.object(
                subject._OriginalPythonGateObserver, "require_current", foreign
            ),
            mock.patch(
                "subprocess.Popen", side_effect=AssertionError("gate started")
            ) as child,
        ):
            for _ in range(2):
                with self.assertRaisesRegex(
                    ValueError, "original_observer_method_changed"
                ):
                    self.run_original(wrapper, interpreter)
            self.assertEqual(calls, [])
            child.assert_not_called()

    def test_current_input_callback_cannot_dispatch_or_rebaseline_foreign_descriptor(
        self,
    ):
        original = subject._OriginalPythonGateObserver.__dict__["require_current"]
        calls, changed = [], []
        native_check = subject.require_original_python_gate_tool
        patch = mock.patch.object(
            subject._OriginalPythonGateObserver,
            "require_current",
            _ForeignDescriptor(original, calls),
        )

        def current(selection, identity):
            native_check(selection, identity)
            if selection.role == "shell" and not changed:
                patch.start()
                changed.append(True)

        try:
            with (
                self.interpreter() as interpreter,
                observed_retained_python_wrapper(
                    self.fx.reviewed, budget=self.fx.budget
                ) as wrapper,
                mock.patch.object(
                    subject, "require_original_python_gate_tool", current
                ),
                mock.patch(
                    "subprocess.Popen", side_effect=AssertionError("gate started")
                ) as child,
            ):
                for _ in range(2):
                    with self.assertRaisesRegex(
                        ValueError, "original_observer_method_changed"
                    ):
                        self.run_original(wrapper, interpreter)
                self.assertEqual(changed, [True])
                self.assertEqual(calls, [])
                child.assert_not_called()
        finally:
            if changed:
                patch.stop()
