"""Actual measured provider tools retained by the private Standard factory.

Only concrete Python/Cargo/Rust roles are implemented by this private completion
route. Public Standard discovery, arbitrary public bindings and other tool roles
remain unchanged. Callback guards cannot be decoded into runtime observations.
"""

import math
import time
from dataclasses import asdict, dataclass, field

from literate_ai.adapters.authored_sdk_product_completion import (
    _capture_authored_sdk_products,
)
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.adapters.builders.python import PythonToolchain
from literate_ai.adapters.builders.rust import RustToolchain
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.contracts.identity import canonical_identity

_KEY = object()
_RAW = {
    PythonToolchain: PythonToolchain._require_files_unchanged,
    CargoToolchain: CargoToolchain._require_files_unchanged,
    RustToolchain: RustToolchain._require_files_unchanged,
}


def _binding_values(binding):
    return (
        binding.executable,
        binding.arguments,
        binding.environment,
        binding.authority_identity,
        binding._initial_identity,
    )


class _UnsavableProviderTools:
    __slots__ = ()

    def __copy__(self):
        raise TypeError("qualification.authored.provider-tools-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("qualification.authored.provider-tools-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("qualification.authored.provider-tools-not-serializable")


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredProviderTools(_UnsavableProviderTools):
    _closure: object = field(repr=False)
    _tools: tuple = field(repr=False)
    _bindings: tuple = field(repr=False)
    _authorities: tuple = field(repr=False)
    _refs: tuple = field(repr=False)
    _sdk: object = field(repr=False)

    def __init__(self, closure, tools, bindings, authorities, refs, sdk, key):
        if key is not _KEY:
            raise TypeError("qualification.authored.original-provider-tools-required")
        for name, value in (
            ("_closure", closure),
            ("_tools", tools),
            ("_bindings", bindings),
            ("_authorities", authorities),
            ("_refs", refs),
            ("_sdk", sdk),
        ):
            object.__setattr__(self, name, value)

    def _require_fields(self):
        if any(getattr(self._closure, name) is not value for name, value in self._refs):
            raise ValueError("qualification.authored.original-provider-tools-changed")
        for _role, tool, original_type, values in self._tools:
            if (
                type(tool) is not original_type
                or canonical_identity(asdict(tool)) != values
            ):
                raise ValueError(
                    "qualification.authored.original-provider-tool-changed"
                )
        for binding, values, guard, _raw in self._bindings:
            if (
                _binding_values(binding) != values
                or binding._authority_guard is not guard
            ):
                raise ValueError(
                    "qualification.authored.original-provider-binding-changed"
                )
        for authority, identity, guard in self._authorities:
            if authority.identity.uri != identity or authority._guard is not guard:
                raise ValueError(
                    "qualification.authored.original-provider-guard-changed"
                )

    def require_original_files(self):
        self._require_fields()
        if self._sdk is not None:
            self._sdk.require_original_files()
        for _role, tool, original_type, _values in self._tools:
            _RAW[original_type](tool)
        for binding, _values, _guard, raw in self._bindings:
            if LocalComponentToolBinding._current_identity(binding) != raw:
                raise ValueError(
                    "qualification.authored.original-provider-binding-changed"
                )
        self._require_fields()

    def refresh_current(self, *, deadline):
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or deadline <= 0
        ):
            raise ValueError("qualification.authored.provider-tool-deadline-invalid")

        def within_deadline():
            if time.monotonic() >= deadline:
                raise ValueError(
                    "qualification.authored.provider-tool-deadline-expired"
                )

        within_deadline()
        self.require_original_files()
        within_deadline()
        self._closure.require_unchanged()
        within_deadline()
        if self._sdk is not None:
            self._sdk.refresh_current(deadline=deadline)
        within_deadline()
        self.require_original_files()
        within_deadline()


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalProjectedStandardSession(_UnsavableProviderTools):
    closure: object
    completion: object
    _key: object = field(repr=False)

    def __post_init__(self):
        if self._key is not _KEY:
            raise TypeError("qualification.authored.original-standard-session-required")


def _retain_original_provider_tools(closure, tools, *, native_sdk_inputs):
    """Called while the actual discovery mapping is still held by its factory."""
    values = []
    for role, tool in sorted(tools.items()):
        if type(tool) not in _RAW:
            raise TypeError("qualification.authored.provider-tool-role-unsupported")
        values.append((role, tool, type(tool), canonical_identity(asdict(tool))))
    result = _OriginalAuthoredProviderTools(
        closure,
        tuple(values),
        tuple(
            (b, _binding_values(b), b._authority_guard, b._initial_identity)
            for b in closure.tool_bindings
        ),
        tuple((a, a.identity.uri, a._guard) for a in closure.toolchain_authorities),
        tuple(
            (name, getattr(closure, name))
            for name in ("tool_bindings", "toolchain_authorities", "dependency_guard")
        ),
        (
            _capture_authored_sdk_products(native_sdk_inputs)
            if native_sdk_inputs is not None
            else None
        ),
        _KEY,
    )
    result.require_original_files()
    return _OriginalProjectedStandardSession(closure, result, _KEY)
