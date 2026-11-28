"""Reopen private operator configuration; wire documents never select trust.

This is observation configuration only. It neither constructs a lifecycle owner
nor accepts an execution capability. Native Windows key-custody policy requires
its own ACL-backed implementation; Unix mode bits are not treated as a DACL.
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts._validation import contract_fields, string_value
from literate_ai.contracts.execution_dispatch import ExecutionWorkerCatalog
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.worker_telemetry_authorization import WorkerTelemetryScope
from literate_ai.projects import PinnedInputClosure
from literate_ai.security.evidence.ed25519 import Ed25519EvidenceSigner

from .action_capabilities import receiver_code_identity
from .action_dispatch_wire import ActionDispatchDeadline, record_identity
from .user_paths import resolve_user_paths
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_native_binding import (
    CurrentNativeResourceProvider,
    load_native_resource_provider,
)
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

_SCHEMA = "literate-ai/private-worker-telemetry-configuration@1"
_NATIVE_SCHEMA = "literate-ai/private-worker-telemetry-configuration@2"
_PROVISIONED_NATIVE_SCHEMA = "literate-ai/private-worker-telemetry-configuration@3"
_SEAL = object()


def _refuse(code: str = "configuration_invalid"):
    raise WorkerTelemetryWireError("worker_telemetry." + code)


def _path(value: object) -> Path:
    text = string_value(value, "WorkerTelemetryConfiguration.path")
    path = Path(text)
    if not path.is_absolute() or "\0" in text or ".." in path.parts:
        _refuse()
    return path


def _file_guard(path: Path, *, private: bool) -> tuple:
    # PinnedInputClosure separately rejects every symlink in the configured path.
    # These guards also bind the file/parent inode and its actual access policy.
    require_safe_directory(path.parent)
    parent = path.parent.lstat()
    node = path.lstat()
    if (
        not stat.S_ISREG(node.st_mode)
        or node.st_nlink != 1
        or node.st_uid != os.geteuid()
        or parent.st_uid != os.geteuid()
        or stat.S_IMODE(node.st_mode) & (0o077 if private else 0o022)
        or stat.S_IMODE(parent.st_mode) & (0o077 if private else 0o022)
    ):
        _refuse("private_input_unsafe")
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_nlink,
        parent.st_dev,
        parent.st_ino,
        parent.st_mode,
        parent.st_uid,
        parent.st_gid,
    )


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class CurrentWorkerTelemetryConfiguration:
    """Actual reopened configuration, not serializable observation permission."""

    role: str
    catalog: ExecutionWorkerCatalog
    scope: WorkerTelemetryScope
    signer: Ed25519EvidenceSigner = field(repr=False)
    registration_identity: ContentIdentity
    receiver_command: tuple[str, ...] | None
    observation_root: Path | None
    observation_namespace_identity: ContentIdentity | None
    protected_parent_configuration: Path | None
    protected_parent_identity: ContentIdentity | None
    native_resources: CurrentNativeResourceProvider | None
    _inputs: PinnedInputClosure = field(repr=False)
    _guards: tuple = field(repr=False)
    _receiver_code: ContentIdentity | None = field(repr=False)
    _seal: object = field(repr=False)

    def __post_init__(self):
        if type(self._seal) is not ObservationIssuance:
            _refuse("current_configuration_required")
        self._seal.require_constructor(self, _SEAL)

    @property
    def worker(self):
        return self.catalog.worker(self.scope.worker_id)

    def require_current(self, *, deadline: ActionDispatchDeadline) -> None:
        if type(self._seal) is not ObservationIssuance:
            _refuse("current_configuration_required")
        self._seal.require_original(self, _SEAL)
        try:
            deadline.remaining()
            for path, private, expected in self._guards:
                if _file_guard(path, private=private) != expected:
                    _refuse("configuration_changed")
            self._inputs.require_unchanged()
            if self.native_resources is not None:
                self.native_resources.require_current()
            if self._receiver_code is not None:
                if receiver_code_identity(deadline=deadline) != self._receiver_code:
                    _refuse("receiver_changed")
            self._inputs.require_unchanged()
            if self.native_resources is not None:
                self.native_resources.require_current()
            for path, private, expected in self._guards:
                if _file_guard(path, private=private) != expected:
                    _refuse("configuration_changed")
            deadline.remaining()
        except WorkerTelemetryWireError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            raise WorkerTelemetryWireError(
                "worker_telemetry.configuration_unavailable"
            ) from exc

    def require_observation_inputs_current(self, *, deadline: ActionDispatchDeadline):
        """Native poller only: operator revocation without a full code-tree walk.

        Full Python/provider code currentness still brackets signed publication.
        Sampling reopens the finite raw operator/config/key/scope closure, while
        its process interrupt guard checks original lifetime and scope expiry.
        """
        if type(self._seal) is not ObservationIssuance:
            _refuse("current_configuration_required")
        self._seal.require_original(self, _SEAL)
        try:
            deadline.remaining()
            now = time.time_ns() // 1_000_000
            if not self.scope.not_before_ms <= now < self.scope.expires_at_ms:
                _refuse("observation_scope_expired")
            for path, private, expected in self._guards:
                if _file_guard(path, private=private) != expected:
                    _refuse("configuration_changed")
            self._inputs.require_unchanged()
            for path, private, expected in self._guards:
                if _file_guard(path, private=private) != expected:
                    _refuse("configuration_changed")
            deadline.remaining()
        except WorkerTelemetryWireError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            raise WorkerTelemetryWireError(
                "worker_telemetry.configuration_unavailable"
            ) from exc

    def __copy__(self):
        _refuse("current_configuration_not_copyable")

    def __deepcopy__(self, memo):
        _refuse("current_configuration_not_copyable")

    def __reduce__(self):
        _refuse("current_configuration_not_restorable")


def load_worker_telemetry_configuration(
    path: Path, *, role: str, deadline: ActionDispatchDeadline
) -> CurrentWorkerTelemetryConfiguration:
    """Load four exact inputs and an optional protected-parent registration.

    Receiver registration excludes the scope itself, avoiding a scope/registration
    hash cycle. Its identity binds the receiver's actual code, selected worker,
    catalog, raw configuration and worker public key. Controllers trust only the
    registration already bound by their current, private operator scope.
    An enabled protected-parent file is pinned as raw bounded bytes; parsing it
    cannot create an attempt owner, and controllers never read that remote path.
    Explicit receiver-only @2 additionally binds a current canonical native
    source and private artifact through its separately bounded provider closure.
    @1 never discovers/provisions that provider or changes its wire shape.
    """
    if role not in ("controller", "receiver"):
        _refuse()
    if os.name != "posix":
        _refuse("native_key_custody_unsupported")
    guards = []
    inputs = PinnedInputClosure(
        maximum_files=5,
        maximum_file_bytes=1024 * 1024,
        maximum_total_bytes=2 * 1024 * 1024,
    )

    def read(selected: Path, label: str, limit: int, *, private: bool) -> bytes:
        deadline.remaining()
        before = _file_guard(selected, private=private)
        part = PinnedInputClosure(
            maximum_files=1,
            maximum_file_bytes=limit,
            maximum_total_bytes=limit,
        )
        raw = part.pin(selected, boundary=selected.parent, label=label)
        if _file_guard(selected, private=private) != before:
            _refuse("configuration_changed")
        inputs.include(part)
        guards.append((selected, private, before))
        return raw

    try:
        path = _path(str(path))
        raw = read(path, "configuration", 64 * 1024, private=True)
        decoded = _decode(raw, 64 * 1024)
        provisioned_version = (
            type(decoded) is dict
            and decoded.get("schema") == _PROVISIONED_NATIVE_SCHEMA
        )
        native_version = (
            type(decoded) is dict and decoded.get("schema") == _NATIVE_SCHEMA
        ) or provisioned_version
        if native_version and role != "receiver":
            _refuse()
        value = contract_fields(
            decoded,
            path="WorkerTelemetryConfiguration",
            schema_uri=(
                _PROVISIONED_NATIVE_SCHEMA
                if provisioned_version
                else _NATIVE_SCHEMA
                if native_version
                else _SCHEMA
            ),
            required=frozenset(
                {
                    "role",
                    "worker_id",
                    "catalog",
                    "scope",
                    "private_key",
                    "receiver_command",
                    "observation_root",
                    "observation_namespace_identity",
                }
                | ({"native_resources"} if native_version else set())
            ),
            optional=frozenset({"protected_parent_configuration"}),
        )
        if value["role"] != role:
            _refuse()
        catalog_path = _path(value["catalog"])
        scope_path = _path(value["scope"])
        key_path = _path(value["private_key"])
        if len({path, catalog_path, scope_path, key_path}) != 4:
            _refuse()
        catalog_value = _decode(
            read(catalog_path, "catalog", 1024 * 1024, private=False), 1024 * 1024
        )
        # Bound nested worker DTO construction before calling the canonical codec.
        if (
            not isinstance(catalog_value, dict)
            or type(catalog_value.get("workers")) is not list
            or len(catalog_value["workers"]) > 256
        ):
            _refuse()
        catalog = ExecutionWorkerCatalog.from_dict(catalog_value)
        worker = catalog.worker(value["worker_id"])
        scope = WorkerTelemetryScope.from_dict(
            _decode(read(scope_path, "scope", 32 * 1024, private=True), 32 * 1024)
        )
        key = read(key_path, "private-key", 32, private=True)
        if len(key) != 32:
            _refuse("private_key_invalid")
        signer = Ed25519EvidenceSigner(key)
        command = value["receiver_command"]
        protected_parent = value.get("protected_parent_configuration")
        protected_identity = None
        observation_root = value["observation_root"]
        namespace_identity = value["observation_namespace_identity"]
        if role == "receiver":
            if (
                command is not None
                or signer.public_key.hex() != scope.worker_public_key
            ):
                _refuse()
            observation_root = _path(observation_root)
            namespace_identity = ContentIdentity.from_dict(namespace_identity)
            if (
                observation_root
                != Path(resolve_user_paths().state_root) / "worker-telemetry"
            ):
                _refuse("observation_namespace_mismatch")
            if protected_parent is not None:
                protected_parent = _path(protected_parent)
                if protected_parent in {path, catalog_path, scope_path, key_path}:
                    _refuse("protected_parent_configuration_invalid")
                protected_identity = record_identity(
                    read(
                        protected_parent,
                        "protected-parent-configuration",
                        65536,  # Exact native receiver registration envelope.
                        private=False,
                    )
                )
        else:
            if (
                type(command) is not list
                or not 1 <= len(command) <= 64
                or any(
                    not isinstance(item, str)
                    or not item
                    or any(c in item for c in ("\0", "\r", "\n"))
                    for item in command
                )
                or sum(len(item.encode("utf-8")) for item in command) > 32768
                or signer.public_key.hex() != scope.controller_public_key
                or observation_root is not None
                or namespace_identity is not None
                or protected_parent is not None
            ):
                _refuse()
            command = tuple(command)
        if (
            scope.worker_id != worker.worker_id
            or scope.worker_identity != worker.identity
            or scope.catalog_identity != catalog.identity
        ):
            _refuse("configured_worker_mismatch")
        if native_version and protected_parent is None:
            _refuse("protected_parent_required")
        if provisioned_version and (
            type(value["native_resources"]) is not dict
            or value["native_resources"].get("schema")
            != "literate-ai/private-worker-telemetry-native-provider@2"
        ):
            _refuse("provisioned_native_provider_required")
        native_resources = (
            load_native_resource_provider(value["native_resources"])
            if native_version
            else None
        )
        code = receiver_code_identity(deadline=deadline) if role == "receiver" else None
        registration = scope.registration_identity
        if code is not None:
            registration_fields = {
                "schema": "literate-ai/worker-telemetry-receiver-registration@1",
                "configuration_identity": record_identity(raw).to_dict(),
                "worker_identity": worker.identity.to_dict(),
                "catalog_identity": catalog.identity.to_dict(),
                "receiver_code_identity": code.to_dict(),
                "worker_public_key": scope.worker_public_key,
            }
            if protected_identity is not None:
                registration_fields["protected_parent_configuration_identity"] = (
                    protected_identity.to_dict()
                )
            if native_resources is not None:
                registration_fields["native_resource_provider_identity"] = (
                    native_resources.identity.to_dict()
                )
            registration = canonical_identity(registration_fields)
        if registration != scope.registration_identity:
            _refuse("registration_mismatch")
        issuance = ObservationIssuance(_SEAL)
        current = CurrentWorkerTelemetryConfiguration(
            role,
            catalog,
            scope,
            signer,
            registration,
            command,
            observation_root,
            namespace_identity,
            protected_parent,
            protected_identity,
            native_resources,
            inputs,
            tuple(guards),
            code,
            issuance,
        )
        issuance.bind(current, _SEAL)
        current.require_current(deadline=deadline)
        return current
    except WorkerTelemetryWireError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise WorkerTelemetryWireError(
            "worker_telemetry.configuration_unavailable"
        ) from exc
