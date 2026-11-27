"""Current, explicitly configured native observation bytes; no provisioning.

Only private receiver configuration@2 can select this provider. Public telemetry
requests cannot supply paths, arguments, code or PIDs. Source and executable are
separate byte bindings: Python receiver-code identity does not cover native code.
This is an operator-authorized observer, not a verified native build receipt.
"""

from __future__ import annotations

import importlib
import os
import platform
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts._validation import contract_fields, int_value
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.projects import PinnedInputClosure

from .user_paths import resolve_user_paths
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError

_ISSUER = object()
_SCHEMA = "literate-ai/private-worker-telemetry-native-provider@1"
_PROVISIONED_SCHEMA = "literate-ai/private-worker-telemetry-native-provider@2"
_SOURCE_DIGEST = "602d4de7d5fd625ecbf1227397a0ef669fd4bfe31f0c8174fc025c8bdf0739ce"
_SOURCE_BYTES = 13998
_MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_provider_unavailable")


def _signature(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_nlink,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
    )


def _guard(path, *, executable):
    require_safe_directory(path.parent)
    parent, node = path.parent.lstat(), path.lstat()
    if (
        not stat.S_ISREG(node.st_mode)
        or node.st_nlink != 1
        or node.st_uid not in ({os.geteuid()} if executable else {0, os.geteuid()})
        or parent.st_uid not in ({os.geteuid()} if executable else {0, os.geteuid()})
        or stat.S_IMODE(node.st_mode) & 0o022
        or stat.S_IMODE(parent.st_mode) & 0o022
        or (executable and not node.st_mode & stat.S_IXUSR)
        or (executable and stat.S_IMODE(parent.st_mode) & 0o077)
        or (executable and stat.S_IMODE(node.st_mode) & 0o077)
    ):
        _refuse()
    return _signature(parent), _signature(node)


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class CurrentNativeResourceProvider:
    """Original reopened operator binding, not reconstructed job authority."""

    executable: Path
    identity: ContentIdentity
    interval_ms: int
    process_timeout_ms: int
    output_limit_bytes: int
    _source: Path = field(repr=False)
    _inputs: PinnedInputClosure = field(repr=False)
    _guards: tuple = field(repr=False)
    _pid: int = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _ISSUER)

    def require_current(self, *, rehash=True):
        self._issuance.require_original(self, _ISSUER)
        if self._pid != os.getpid() or not sys.platform.startswith("freebsd"):
            _refuse()
        try:
            for path, executable, expected in self._guards:
                if _guard(path, executable=executable) != expected:
                    _refuse()
            if rehash:
                self._inputs.require_unchanged()
                for path, executable, expected in self._guards:
                    if _guard(path, executable=executable) != expected:
                        _refuse()
        except (OSError, ValueError, RuntimeError) as exc:
            raise WorkerTelemetryWireError(
                "worker_telemetry.native_provider_unavailable"
            ) from exc

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


def load_native_resource_provider(value):
    """Private configuration loader only; never called from a wire frame."""
    if os.name != "posix" or not sys.platform.startswith("freebsd"):
        _refuse()
    provisioned = type(value) is dict and value.get("schema") == _PROVISIONED_SCHEMA
    selected = contract_fields(
        value,
        path="NativeResourceProvider",
        schema_uri=_PROVISIONED_SCHEMA if provisioned else _SCHEMA,
        required=frozenset(
            {
                "source_identity",
                "artifact_identity",
                "artifact_size_bytes",
                "interval_ms",
                "process_timeout_ms",
                "output_limit_bytes",
            }
            | ({"provision_identity"} if provisioned else set())
        ),
    )
    source_identity = ContentIdentity.from_dict(selected["source_identity"])
    if source_identity.digest != _SOURCE_DIGEST:
        _refuse()
    artifact_identity = ContentIdentity.from_dict(selected["artifact_identity"])
    size = int_value(
        selected["artifact_size_bytes"], "native.artifact_size_bytes", minimum=64
    )
    if size > _MAX_ARTIFACT_BYTES:
        _refuse()
    # Fixed operator-owned namespace, not an authored project or wire path.
    executable = (
        Path(resolve_user_paths().state_root)
        / "worker-telemetry-native-providers"
        / artifact_identity.digest
        / "freebsd-resource-snapshot"
    )
    interval = int_value(selected["interval_ms"], "native.interval_ms", minimum=1000)
    timeout = int_value(
        selected["process_timeout_ms"], "native.process_timeout_ms", minimum=2000
    )
    output_limit = int_value(
        selected["output_limit_bytes"], "native.output_limit_bytes", minimum=1024
    )
    if interval > 30000 or timeout > 5000 or output_limit > 96 * 1024:
        _refuse()
    source = Path(__file__).resolve().parents[1] / "native/freebsd_telemetry_snapshot.c"
    if source == executable:
        _refuse()
    inputs = PinnedInputClosure(
        maximum_files=7 if provisioned else 2,
        maximum_file_bytes=8 * 1024 * 1024 if provisioned else _MAX_ARTIFACT_BYTES,
        maximum_total_bytes=13 * 1024 * 1024
        if provisioned
        else _MAX_ARTIFACT_BYTES + 64 * 1024,
    )
    guards = []
    if provisioned:
        from .worker_telemetry_native_provision import read_native_provider_provision

        provision_identity = ContentIdentity.from_dict(selected["provision_identity"])
        proof, proof_inputs = read_native_provider_provision(
            executable.parent, expected_provision_identity=provision_identity
        )
        if (
            proof["artifact_identity"] != artifact_identity.uri
            or proof["source_identity"] != source_identity.uri
            or proof["artifact_size_bytes"] != size
        ):
            _refuse()
        inputs.include(proof_inputs)
        for name in (
            "build-observation.json",
            "native-probe-observation.json",
            "native-probe-guardian.json",
            "provision.json",
        ):
            receipt_path = executable.parent / name
            guards.append((receipt_path, False, _guard(receipt_path, executable=False)))
    contents = []
    for path, expected, expected_size, is_executable, label in (
        (source, source_identity, _SOURCE_BYTES, False, "native-source"),
        (executable, artifact_identity, size, True, "native-artifact"),
    ):
        guard = _guard(path, executable=is_executable)
        raw = inputs.pin(
            path, boundary=path.parent, label=label, expected_identity=expected
        )
        if len(raw) != expected_size or _guard(path, executable=is_executable) != guard:
            _refuse()
        guards.append((path, is_executable, guard))
        contents.append(raw)
    # Native class/endian/machine/OS ABI are actual file facts, not host labels.
    native_machine = {"amd64": 62, "x86_64": 62, "aarch64": 183, "arm64": 183}.get(
        platform.machine().lower()
    )
    binary = contents[1]
    if (
        native_machine is None
        or binary[:4] != b"\x7fELF"
        or binary[4:8] != bytes((2, 1, 1, 9))
        or int.from_bytes(binary[18:20], "little") != native_machine
        or int.from_bytes(binary[16:18], "little") not in (2, 3)
    ):
        _refuse()
    # Prepare trusted Python module bytes outside any actual execution/runner
    # push path. Its module body launches nothing; @1 never reaches this load.
    importlib.import_module("literate_ai.adapters.worker_telemetry_native_measurement")
    issuance = ObservationIssuance(_ISSUER)
    provider = CurrentNativeResourceProvider(
        executable,
        canonical_identity(value),
        interval,
        timeout,
        output_limit,
        source,
        inputs,
        tuple(guards),
        os.getpid(),
        issuance,
    )
    issuance.bind(provider, _ISSUER)
    provider.require_current()
    return provider
