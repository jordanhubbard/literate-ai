"""Original concrete consumer tools for one private completion operation.

Full probes and arbitrary independently supplied guards belong before final
local comparisons. No SDK closure is inferred from a callback or identity, and
these observations cannot authorize execution or complete an admission.
"""

from dataclasses import dataclass, field

from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    AuthoredRetainedCargoExecutionInputs,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.adapters.builders.rust import RustToolchain
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
    _UnsavableNativePreparation,
)

_KEY = object()
_CARGO_FIELDS = (
    "command",
    "launcher_executable",
    "launcher_digest",
    "version",
    "version_info",
    "identity",
)
_RUST_FIELDS = (
    "command",
    "launcher_executable",
    "launcher_digest",
    "compiler_executable",
    "compiler_digest",
    "version",
    "identity",
)


def _fields(owner, names):
    return tuple(getattr(owner, name) for name in names)


def _binding_fields(tool):
    return (
        tool.executable,
        tool.arguments,
        tool.environment,
        tool.authority_identity,
        tool._initial_identity,
        tool._authority_guard,
    )


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredConsumerTools(_UnsavableNativePreparation):
    _inputs: object = field(repr=False)
    _current: object = field(repr=False)
    _cargo: object = field(repr=False)
    _rustc: object = field(repr=False)
    _cargo_fields: tuple = field(repr=False)
    _rust_fields: tuple = field(repr=False)
    _bindings: tuple = field(repr=False)
    _deadline: float = field(repr=False)

    def __init__(self, inputs, cargo, rustc, bindings, deadline, key):
        if key is not _KEY:
            raise TypeError("retained.completion.original-consumer-tools-required")
        current = inputs.materialized.current
        for name, value in (
            ("_inputs", inputs),
            ("_current", current),
            ("_cargo", cargo),
            ("_rustc", rustc),
            ("_cargo_fields", _fields(cargo, _CARGO_FIELDS)),
            ("_rust_fields", _fields(rustc, _RUST_FIELDS)),
            ("_bindings", bindings),
            ("_deadline", deadline),
        ):
            object.__setattr__(self, name, value)

    def require_original_files(self):
        """Original launcher/compiler bytes and binding fields; no callbacks.

        Parent binding identity computation retains the existing local-command
        byte/argument/environment semantics, including its existing read size.
        Subclasses retain their original full guards; no callback internals are
        inspected and no native SDK authority is inferred.
        """
        if (
            self._inputs.materialized.current is not self._current
            or self._current.cargo is not self._cargo
            or self._current.rustc is not self._rustc
            or _fields(self._cargo, _CARGO_FIELDS) != self._cargo_fields
            or _fields(self._rustc, _RUST_FIELDS) != self._rust_fields
        ):
            raise ValueError("retained.completion.original-consumer-tool-owner-changed")
        self._cargo._require_files_unchanged()
        self._rustc._require_files_unchanged()
        for _token, tool, fields, raw_identity in self._bindings:
            if (
                _binding_fields(tool)[:-1] != fields[:-1]
                or tool._authority_guard is not fields[-1]
                or (LocalComponentToolBinding._current_identity(tool) != raw_identity)
            ):
                raise ValueError("retained.completion.original-tool-binding-changed")

    def refresh_current(self):
        """Full original probes/guards, then raw facts, under original deadline.

        Guards may execute tools or consult policy. An expired guard refuses;
        this code never catches it to restore authority. The owning operation
        still must close all scopes and finish its remaining original facts.
        """
        _require_native_completion_deadline(self._deadline)
        self.require_original_files()
        for tool in (self._cargo, self._rustc):
            _require_native_completion_deadline(self._deadline)
            tool.require_unchanged()
            _require_native_completion_deadline(self._deadline)
        for _token, tool, fields_before, _identity in self._bindings:
            _require_native_completion_deadline(self._deadline)
            if tool._authority_guard is not fields_before[-1]:
                raise ValueError("retained.completion.original-tool-guard-changed")
            tool.require_unchanged()
            if tool._authority_guard is not fields_before[-1]:
                raise ValueError("retained.completion.original-tool-guard-changed")
            _require_native_completion_deadline(self._deadline)
        self.require_original_files()
        _require_native_completion_deadline(self._deadline)


def _capture_authored_consumer_tools(
    inputs,
    *,
    cargo,
    rustc,
    gate_tools,
    environment,
    deadline,
):
    """Capture actual consumed objects before execution, never after closure.

    The actual execution core owns gate-token membership and reviewed bindings;
    this private comparison supplies neither those permissions nor a new clock.
    """
    if type(inputs) is not AuthoredRetainedCargoExecutionInputs:
        raise TypeError("retained.completion.original-authored-inputs-required")
    current = inputs.materialized.current
    if (
        type(current) is not CurrentAuthoredRetainedCargoInputs
        or type(current.cargo) is not CargoToolchain
        or type(current.rustc) is not RustToolchain
    ):
        raise TypeError("retained.completion.original-consumer-tool-pair-required")
    _require_native_completion_deadline(deadline)
    tools = (("cargo", cargo), ("rustc", rustc), *tuple(sorted(gate_tools.items())))
    if any(not isinstance(tool, LocalComponentToolBinding) for _, tool in tools):
        raise TypeError("retained.completion.original-tool-bindings-required")
    bindings = tuple(
        (
            token,
            tool,
            _binding_fields(tool),
            LocalComponentToolBinding._current_identity(tool),
        )
        for token, tool in tools
    )
    result = _OriginalAuthoredConsumerTools(
        inputs,
        current.cargo,
        current.rustc,
        bindings,
        deadline,
        _KEY,
    )
    # Validate the actual still-live input owner only after retaining original
    # fields, so its callbacks cannot choose a replacement expected tool state.
    inputs.current_identity(environment=environment)
    result.refresh_current()
    return result
