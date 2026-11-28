"""Fixed private observation files, independent of every execution reservation.

This POSIX backend starts with one nonblocking global collector lease, below the
configured concurrency ceiling. Live descriptors only locate challenge slots;
they never grant ownership. Missing/replaced initialized files refuse. No caller
path, PID, arbitrary sink or mutable execution handle enters this boundary.
"""

from __future__ import annotations

import os
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime

from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.worker_telemetry_v2 import MAX_REQUEST_BYTES

from .worker_telemetry_claims import (
    require_announced,
    require_unpoisoned,
    selector_digest,
)
from .worker_telemetry_configuration import CurrentWorkerTelemetryConfiguration
from .worker_telemetry_contributions import MAX_CONTRIBUTION_BYTES
from .worker_telemetry_namespace import (
    node_wire,
    open_file,
    open_worker_telemetry_namespace,
    private,
    refuse,
    require_file,
    write_at,
)
from .worker_telemetry_owner import (
    ConfiguredWorkerTelemetryPublisher,
    LiveWorkerTelemetryOwner,
)
from .worker_telemetry_replay import _locked
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

MAX_LIVE_OWNER_SLOTS = 64
_MARKER_BYTES = 2048
_DESCRIPTOR_BYTES = 2048
_REQUEST_BYTES = MAX_REQUEST_BYTES + 65
_DESCRIPTOR_SCHEMA = "literate-ai/private-worker-telemetry-live-descriptor@2"
_FILES = frozenset(
    {".owner", ".lease", ".io", ".conflict", "descriptor", "request", "response"}
)


def require_unambiguous_slot(files):
    # Monotonic for this exact operation selector. No PID/age/history can clear
    # conflict or select a preferred publisher. Unknown contents also refuse.
    if files[".conflict"].read() != b"":
        refuse("owner_ambiguous")


def _mark_conflict(files, owner):
    ends = time.monotonic() + 30
    while time.monotonic() < ends:
        owner.require_open()
        try:
            with _locked(files[".io"].descriptor):
                owner.require_open()
                files[".conflict"].write(b"1")
                return
        except WorkerTelemetryWireError as exc:
            if exc.code != "worker_telemetry.observation_overloaded":
                raise
            time.sleep(0.01)
    refuse("observation_overloaded")


def owner_slot_name(configuration, operation_identity):
    return "o-" + selector_digest(configuration, operation_identity)


def _signature(node):
    return (*node_wire(node), node.st_size, node.st_mtime_ns, node.st_ctime_ns)


class _RegularSlotFile:
    def __init__(self, directory, name, descriptor, expected, maximum, current):
        self.directory = directory
        self.name = name
        self.descriptor = descriptor
        self.expected = expected
        self.maximum = maximum
        self.current = current

    def require_current(self):
        self.current()
        size = os.fstat(self.descriptor).st_size
        if not 0 <= size <= self.maximum:
            refuse("slot_limit")
        require_file(
            self.directory,
            self.name,
            self.descriptor,
            expected=self.expected,
            size=size,
        )

    def read(self):
        self.require_current()
        before = os.fstat(self.descriptor)
        raw = os.pread(self.descriptor, self.maximum + 1, 0)
        after = os.fstat(self.descriptor)
        self.require_current()
        if len(raw) != before.st_size or _signature(before) != _signature(after):
            refuse("slot_changed")
        return raw

    def write(self, raw):
        # Called only under this slot's separate observer publication lock.
        if type(raw) is not bytes or len(raw) > self.maximum:
            refuse("slot_limit")
        self.require_current()
        write_at(self.descriptor, raw, 0)
        os.ftruncate(self.descriptor, len(raw))
        os.fsync(self.descriptor)
        self.require_current()


@contextmanager
def live_slot_directory(configuration, operation_identity, *, create=False):
    """Open one exact bounded slot; creation never replaces an initialized peer.

    A caller creating/publishing an owner must separately prove the actual live
    owner and hold its observation lease. Readers gain no owner from this helper.
    """
    name = owner_slot_name(configuration, operation_identity)
    with (
        open_worker_telemetry_namespace(configuration) as (
            _root,
            lock,
            _allocation,
            live,
            claim_lock,
            claims,
            poison,
            namespace_current,
        ),
        ExitStack() as stack,
    ):
        # This is the exact descriptor attested/guarded by the namespace owner.
        # A second open could race replacement/restoration of the named path.
        private(os.fstat(live), directory=True)
        require_unpoisoned(poison, selector_digest(configuration, operation_identity))
        initialization = stack.enter_context(ExitStack())
        created = False
        if create:
            try:
                os.stat(name, dir_fd=live, follow_symlinks=False)
                missing = False
            except FileNotFoundError:
                missing = True
            # Only new directory allocation needs the global namespace lock.
            # An actual duplicate must be able to poison an existing selector
            # while the collector signs/revalidates under its own global lease.
            if missing:
                initialization.enter_context(_locked(lock))
            namespace_current()
            with os.scandir(live) as entries:
                count = 0
                for entry in entries:
                    count += 1
                    if (
                        count > MAX_LIVE_OWNER_SLOTS
                        or len(entry.name) != 66
                        or not entry.name.startswith("o-")
                        or any(c not in "0123456789abcdef" for c in entry.name[2:])
                    ):
                        refuse("slot_namespace_foreign")
            try:
                os.stat(name, dir_fd=live, follow_symlinks=False)
            except FileNotFoundError:
                if not missing:
                    refuse("slot_changed")
                if count >= MAX_LIVE_OWNER_SLOTS:
                    refuse("slot_limit")
                os.mkdir(name, 0o700, dir_fd=live)
                created = True
            namespace_current()
        directory = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=live,
        )
        stack.callback(os.close, directory)
        node = os.fstat(directory)
        private(node, directory=True)
        if created:
            nodes = {}
            for filename in sorted(_FILES - {".owner"}):
                descriptor = open_file(directory, filename, create=True)
                try:
                    os.fsync(descriptor)
                    nodes[filename] = node_wire(os.fstat(descriptor))
                finally:
                    os.close(descriptor)
            raw = canonical_json_bytes(
                {
                    "schema": "literate-ai/private-worker-telemetry-owner-slot@1",
                    "namespace_identity": (
                        configuration.observation_namespace_identity.to_dict()
                    ),
                    "registration_identity": (
                        configuration.registration_identity.to_dict()
                    ),
                    "operation_identity": operation_identity.to_dict(),
                    "directory": node_wire(node),
                    "files": nodes,
                }
            )
            if len(raw) > _MARKER_BYTES:
                refuse("slot_limit")
            descriptor = open_file(directory, ".owner", create=True)
            try:
                write_at(descriptor, raw, 0)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.fsync(directory)
            os.fsync(live)
        # New-slot allocation remains locked until its complete marker exists.
        # No execution path waits for this asynchronous initialization.
        initialization.close()
        marker = open_file(directory, ".owner")
        stack.callback(os.close, marker)
        marker_node = os.fstat(marker)
        if not 1 <= marker_node.st_size <= _MARKER_BYTES:
            refuse("slot_foreign")
        raw = os.pread(marker, _MARKER_BYTES + 1, 0)
        value = _decode(raw, _MARKER_BYTES)
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "schema",
                "namespace_identity",
                "registration_identity",
                "operation_identity",
                "directory",
                "files",
            }
            or value["schema"] != "literate-ai/private-worker-telemetry-owner-slot@1"
            or value["namespace_identity"]
            != configuration.observation_namespace_identity.to_dict()
            or value["registration_identity"]
            != configuration.registration_identity.to_dict()
            or value["operation_identity"] != operation_identity.to_dict()
            or value["directory"] != node_wire(node)
            or not isinstance(value["files"], dict)
            or set(value["files"]) != _FILES - {".owner"}
        ):
            refuse("slot_foreign")
        with os.scandir(directory) as entries:
            for count, entry in enumerate(entries):
                if count >= len(_FILES) or entry.name not in _FILES:
                    refuse("slot_foreign")

        def current():
            namespace_current()
            require_unpoisoned(
                poison, selector_digest(configuration, operation_identity)
            )
            private(os.fstat(directory), directory=True)
            if (
                node_wire(os.fstat(directory)) != value["directory"]
                or node_wire(os.stat(name, dir_fd=live, follow_symlinks=False))
                != value["directory"]
            ):
                refuse("slot_changed")
            require_file(
                directory,
                ".owner",
                marker,
                expected=node_wire(marker_node),
                size=len(raw),
            )
            if os.pread(marker, _MARKER_BYTES + 1, 0) != raw:
                refuse("slot_changed")

        files = {}
        for filename, maximum in (
            (".lease", 0),
            (".io", 0),
            (".conflict", 1),
            ("descriptor", _DESCRIPTOR_BYTES),
            ("request", _REQUEST_BYTES),
            ("response", MAX_CONTRIBUTION_BYTES),
        ):
            descriptor = open_file(directory, filename)
            stack.callback(os.close, descriptor)
            files[filename] = _RegularSlotFile(
                directory,
                filename,
                descriptor,
                value["files"][filename],
                maximum,
                current,
            )
            files[filename].require_current()
        current()

        def claim_current(publisher_epoch, owner_epoch, index):
            require_announced(
                claim_lock,
                claims,
                poison,
                namespace_current,
                configuration,
                operation_identity,
                index,
                publisher_epoch,
                owner_epoch,
            )

        yield files, current, claim_current
        current()


@contextmanager
def claim_actual_owner_slot(publisher, owner):
    if (
        type(publisher) is not ConfiguredWorkerTelemetryPublisher
        or type(owner) is not LiveWorkerTelemetryOwner
    ):
        refuse("live_owner_required")
    publisher._require_local()
    configuration = publisher._configuration
    if (
        type(configuration) is not CurrentWorkerTelemetryConfiguration
        or configuration.role != "receiver"
    ):
        refuse("receiver_configuration_required")
    owner.require_open()
    request = owner._admission.request
    scope = configuration.scope
    if (
        request.worker.worker_id != scope.worker_id
        or request.worker.worker_identity != scope.worker_identity
        or request.worker.catalog_identity != scope.catalog_identity
        or request.identity not in scope.operation_identities
        or not scope.not_before_ms
        <= int(datetime.now(UTC).timestamp() * 1000)
        < scope.expires_at_ms
    ):
        refuse("actual_operation_scope_mismatch")
    # Reopen current configuration/code outside the tiny observation registry
    # lock, never under a worker's execution or result mutation lock.
    configuration.require_current(deadline=owner._admission.deadline)
    if not publisher._lock.acquire(blocking=False):
        refuse("observation_overloaded")
    try:
        if publisher._owners.get(owner.operation_identity) is not owner:
            refuse("owner_publisher_mismatch")
    finally:
        publisher._lock.release()
    publisher_epoch = publisher._epoch
    announcement = owner._announcement
    announcement.require_original(publisher, owner)
    with live_slot_directory(configuration, owner.operation_identity, create=True) as (
        files,
        current,
        claim_current,
    ):
        claim_current(publisher_epoch, owner._identity, announcement.index)
        with ExitStack() as lease:
            try:
                lease.enter_context(_locked(files[".lease"].descriptor))
            except WorkerTelemetryWireError as exc:
                if exc.code == "worker_telemetry.observation_overloaded":
                    _mark_conflict(files, owner)
                    refuse("owner_ambiguous")
                raise
            files[".lease"].require_current()
            owner.require_open()
            with _locked(files[".io"].descriptor):
                require_unambiguous_slot(files)
                if files["descriptor"].read():
                    files[".conflict"].write(b"1")
                    refuse("owner_ambiguous")
                for name in ("request", "response"):
                    files[name].write(b"")
                files["descriptor"].write(
                    canonical_json_bytes(
                        {
                            "schema": _DESCRIPTOR_SCHEMA,
                            "operation_identity": owner.operation_identity.to_dict(),
                            "action_identity": owner.action_identity.to_dict(),
                            "publisher_epoch": publisher_epoch.to_dict(),
                            "owner_epoch": owner._identity.to_dict(),
                            "claim_index": announcement.index,
                            "reservation_identity": None
                            if owner._admission.reservation_identity is None
                            else owner._admission.reservation_identity.to_dict(),
                        }
                    )
                )
            owner.require_open()
            current()

            def actual_current():
                current()
                require_unambiguous_slot(files)
                owner.require_open()

            actual_current()
            yield files, actual_current
            # No job/result publication joins this context. Its background owner
            # releases only observation locks after any owned file I/O quiesces.
