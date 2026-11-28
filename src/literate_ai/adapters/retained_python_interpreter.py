"""Observe an independently pinned running Python without starting a tool.

This observation grants no execution, provider qualification or consumer admission.
The complete bridge must separately join current provider and consumer authority.
Other interpreters require an acknowledged native selection; their metadata is
never inferred from this process or accepted from a decoded success record.
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from weakref import WeakKeyDictionary

from literate_ai.adapters.builders.python import (
    PythonToolchain,
    _resolved_python_command,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.projects import PinnedInputClosure

_KEY = object()
_OWNERS = WeakKeyDictionary()


def require_retained_python_interpreter(observation, expected_identity):
    """Require the original live observation, never a lookalike tool or callback.

    The expected identity still belongs to independently resolved current input
    authority. This check grants neither execution nor provider admission.
    """
    if (
        type(observation) is not _RetainedPythonInterpreterObservation
        or type(expected_identity) is not ContentIdentity
    ):
        raise TypeError("retained.python.original-interpreter-required")
    observation.require_unchanged()
    if observation.identity != expected_identity.uri:
        raise ValueError("retained.python.interpreter-identity-mismatch")
    observation.require_unchanged()


def _runtime_metadata():
    return (
        sys.implementation.name,
        sys.version,
        tuple(sys.version_info),
        sys.implementation.cache_tag,
    )


@dataclass(frozen=True, slots=True, init=False, eq=False, weakref_slot=True)
class _RetainedPythonInterpreterObservation:
    _tool: object
    _check: object

    def __init__(self, tool, check, key):
        if key is not _KEY:
            raise TypeError("retained.python.original-interpreter-required")
        object.__setattr__(self, "_tool", tool)
        object.__setattr__(self, "_check", check)

    def __copy__(self):
        raise TypeError("retained.python.interpreter-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.python.interpreter-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.python.interpreter-not-serializable")

    def require_unchanged(self):
        check = (
            _OWNERS.get(self)
            if type(self) is _RetainedPythonInterpreterObservation
            else None
        )
        if check is None:
            raise ValueError("retained.python.interpreter-observation-ended")
        check(self)

    @property
    def identity(self):
        self.require_unchanged()
        return self._tool.identity

    @property
    def command(self):
        self.require_unchanged()
        return self._tool.command


@contextmanager
def observed_retained_python_interpreter(
    command: tuple[str, ...],
    *,
    expected_identity: ContentIdentity,
    maximum_file_bytes: int,
    maximum_metadata_bytes: int,
    environment=None,
):
    """Compare an independently reviewed identity using this running runtime.

    The required expected identity must come from current importer/qualified
    interpreter authority, separately from a candidate archive. Matching this
    observation alone supplies no such authority. Only a single executable with
    the same resolved launcher as this process is supported here: shims, command
    flags and foreign runtimes cannot be certified without executing them.
    Bounded original runtime-byte and command-name observations remain fresh
    through scope closure. This is file continuity against a separate pin, not
    the native version-probe authorization required by an execution owner.
    """
    if (
        type(command) is not tuple
        or len(command) != 1
        or type(command[0]) is not str
        or not command[0]
        or type(expected_identity) is not ContentIdentity
        or type(maximum_file_bytes) is not int
        or not 0 < maximum_file_bytes <= 256 * 1024**2
        or type(maximum_metadata_bytes) is not int
        or not 65536 < maximum_metadata_bytes <= 1024**3
    ):
        raise ValueError("retained.python.interpreter-selection-invalid")
    configured = dict(os.environ if environment is None else environment)
    selected, launcher = _resolved_python_command(command, configured)
    invocation = sys.executable
    running = Path(invocation).resolve(strict=True)
    if launcher != running:
        raise ValueError("retained.python.nonrunning-interpreter-unsupported")
    metadata = _runtime_metadata()
    # The existing bounded native input reader retains original bytes. Reserve
    # old/new read chunks, their joined bodies and finite bookkeeping before
    # reading; never fall through to the builder's unbounded executable hasher.
    limit = min(maximum_file_bytes, (maximum_metadata_bytes - 65536) // 4)
    inputs = PinnedInputClosure(
        maximum_files=1,
        maximum_file_bytes=limit,
        maximum_total_bytes=limit,
    )
    content = inputs.pin(
        running, boundary=running.parent, label="retained-python-runtime"
    )
    input_fields = (
        "maximum_files",
        "maximum_file_bytes",
        "maximum_total_bytes",
        "_entries",
        "_total_bytes",
        "_labels",
    )
    input_refs = tuple(getattr(inputs, name) for name in input_fields)
    input_key, input_entry = next(iter(inputs._entries.items()))
    entry_refs = tuple(
        getattr(input_entry, name) for name in ("path", "boundary", "content", "labels")
    )
    input_paths = str(input_entry.path), str(input_entry.boundary)
    labels = tuple(inputs._labels.items())
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    tool = PythonToolchain(
        command=selected,
        launcher_executable=str(launcher),
        launcher_digest=digest,
        runtime_executable=str(running),
        runtime_digest=digest,
        implementation=metadata[0],
        version=metadata[1],
        version_info=metadata[2],
        cache_tag=metadata[3],
    )
    expected = expected_identity.uri
    if tool.identity != expected:
        raise ValueError("retained.python.interpreter-identity-mismatch")
    original = canonical_identity(asdict(tool))
    active = True
    checking = False

    def fields_current(candidate):
        if not active:
            raise ValueError("retained.python.interpreter-observation-ended")
        if (
            candidate is not owner
            or candidate._tool is not tool
            or candidate._check is not check
            or type(tool) is not PythonToolchain
            or canonical_identity(asdict(tool)) != original
            or _runtime_metadata() != metadata
            or sys.executable != invocation
            or expected_identity.uri != expected
            or _OWNERS.get(owner) is not check
            or any(
                getattr(inputs, name) is not original
                for name, original in zip(input_fields, input_refs, strict=True)
            )
            or len(inputs._entries) != 1
            or inputs._entries.get(input_key) is not input_entry
            or any(
                getattr(input_entry, name) is not original
                for name, original in zip(
                    ("path", "boundary", "content", "labels"), entry_refs, strict=True
                )
            )
            or (str(input_entry.path), str(input_entry.boundary)) != input_paths
            or len(inputs._labels) != 1
            or tuple(inputs._labels.items()) != labels
        ):
            raise ValueError("retained.python.original-interpreter-changed")

    def check(candidate):
        nonlocal checking
        if checking:
            raise ValueError("retained.python.reentrant-interpreter-observation")
        checking = True
        try:
            fields_current(candidate)
            selected_now, launcher_now = _resolved_python_command(command, configured)
            if selected_now != selected or launcher_now != launcher:
                raise ValueError("retained.python.interpreter-selection-changed")
            inputs.require_unchanged()
            selected_now, launcher_now = _resolved_python_command(command, configured)
            if selected_now != selected or launcher_now != launcher:
                raise ValueError("retained.python.interpreter-selection-changed")
            fields_current(candidate)
        finally:
            checking = False

    owner = _RetainedPythonInterpreterObservation(tool, check, _KEY)
    _OWNERS[owner] = check
    try:
        owner.require_unchanged()
        yield owner
        owner.require_unchanged()
    finally:
        active = False
        _OWNERS.pop(owner, None)
