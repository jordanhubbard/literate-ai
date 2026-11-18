"""Original-launch native observations, separate from action permission/transport.

The builder alone registers its just-created Popen before publishing/waiting it.
No PID/path lookup API, saved-record decoder or process-control handle is exposed.
Linux samples cover one launched process, NOT its subtree, action or worker. Native
tree attribution and action/reservation admission remain separate receiver work.

Kernel field semantics: https://www.kernel.org/doc/html/latest/filesystems/proc.html
RSS is an estimate; write_bytes accounts at page dirtying, not completed physical
writeout. Preserve cancelled_write_bytes separately rather than inventing net I/O.
"""

from __future__ import annotations

import os
import secrets
import select
import subprocess
import sys
import threading
import time
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass

from literate_ai.contracts._validation import int_value
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

_CURRENT = ContextVar("literate_ai_original_process_observations", default=None)
_ISSUER = object()
_MAX_RECORD = 4096
_MAX_VALUE = (1 << 63) - 1


class NativeProcessObservationError(ValueError):
    pass


def _fail(reason):
    raise NativeProcessObservationError("worker.telemetry_process_" + reason)


def _read_record(directory, name):
    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory)
    try:
        value = os.read(fd, _MAX_RECORD + 1)
        if len(value) > _MAX_RECORD:
            _fail("record_limit")
        return value
    finally:
        os.close(fd)


def _stat_record(content):
    # comm can contain whitespace, newlines and parentheses. Never retain it.
    pid, separator, tail = content.partition(b" (")
    _, end, fields = tail.rpartition(b") ")
    if not separator or not end:
        _fail("stat_invalid")
    values = fields.split()
    if len(values) < 22 or values[0] in (b"Z", b"X", b"x"):
        _fail("not_live")
    observed = tuple(
        int(v) for v in (pid, values[11], values[12], values[19], values[21])
    )
    if any(v < 0 or v > _MAX_VALUE for v in observed):
        _fail("stat_invalid")
    return observed


def _io_record(content):
    required = {
        b"rchar",
        b"wchar",
        b"syscr",
        b"syscw",
        b"read_bytes",
        b"write_bytes",
        b"cancelled_write_bytes",
    }
    values = {}
    for line in content.splitlines():
        key, separator, value = line.partition(b": ")
        if not separator or key in values or key not in required:
            _fail("io_invalid")
        values[key] = int(value)
    if set(values) != required or any(v < 0 or v > _MAX_VALUE for v in values.values()):
        _fail("io_invalid")
    return values


@dataclass(frozen=True, slots=True)
class NativeProcessCounters:
    """Current single-process counters; these confer no live/action authority."""

    launch_identity: ContentIdentity
    process_start_identity: ContentIdentity
    observed_monotonic_ns: int
    user_cpu_time_ns: int
    system_cpu_time_ns: int
    rss_estimate_bytes: int
    storage_read_bytes: int
    storage_write_accounted_bytes: int
    storage_cancelled_write_bytes: int


class _LinuxProcessProbe:
    def __init__(self, directory, pidfd, identity, *, _issuer):
        if _issuer is not _ISSUER:
            _fail("original_launch_required")
        self._directory, self._pidfd = directory, pidfd
        self._start_ticks, self._identity = None, identity
        self._ticks = os.sysconf("SC_CLK_TCK")
        self._page = os.sysconf("SC_PAGE_SIZE")
        if self._ticks <= 0 or self._page <= 0:
            _fail("native_units_unavailable")
        self._lock = threading.Lock()
        self._closed = False

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_process_owner_not_serializable")

    @property
    def identity(self):
        return self._identity

    @property
    def closed(self):
        return self._closed

    def _require_live(self):
        if self._closed or self._pidfd is None:
            _fail("closed")
        poll = select.poll()
        poll.register(self._pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if poll.poll(0):
            _fail("not_live")

    def _release_descriptors(self):
        for name in ("_directory", "_pidfd"):
            fd = getattr(self, name)
            setattr(self, name, None)
            if fd is not None:
                with suppress(OSError):
                    os.close(fd)

    def close(self):
        # Never wait for a collector from the job's completion/cleanup path.
        self._closed = True
        if self._lock.acquire(blocking=False):
            try:
                self._release_descriptors()
            finally:
                self._lock.release()

    def sample(self):
        if not self._lock.acquire(blocking=False):
            _fail("busy")
        try:
            self._require_live()
            before = _stat_record(_read_record(self._directory, "stat"))
            io = _io_record(_read_record(self._directory, "io"))
            after = _stat_record(_read_record(self._directory, "stat"))
            self._require_live()
            if before[3] != after[3] or (
                self._start_ticks is not None and before[3] != self._start_ticks
            ):
                _fail("start_changed")
            self._start_ticks = before[3]
            values = (
                after[1] * 1_000_000_000 // self._ticks,
                after[2] * 1_000_000_000 // self._ticks,
                after[4] * self._page,
                io[b"read_bytes"],
                io[b"write_bytes"],
                io[b"cancelled_write_bytes"],
            )
            if any(v > _MAX_VALUE for v in values):
                _fail("counter_limit")
            start_identity = canonical_identity(
                {"original_launch": self._identity.uri, "native_start_ticks": before[3]}
            )
            return NativeProcessCounters(
                self._identity, start_identity, time.monotonic_ns(), *values
            )
        except Exception:
            # Native errors and task names/paths never enter observation diagnostics.
            raise NativeProcessObservationError(
                "worker.telemetry_process_unavailable"
            ) from None
        finally:
            if self._closed:
                self._release_descriptors()
            self._lock.release()
            # Close may have raced after the check while this lock was held.
            # Recheck after unlock; neither the job nor a closer waits for reads.
            if self._closed:
                self.close()


def _capture_original_launch(process, epoch):
    if type(process) is not subprocess.Popen:
        _fail("original_launch_required")
    if (
        not sys.platform.startswith("linux")
        or not hasattr(os, "pidfd_open")
        or sys.maxsize < (1 << 32)
    ):
        _fail("unsupported")
    directory = pidfd = None
    try:
        # Called immediately after original spawn, before the builder starts waiters.
        # The original child has not been reaped; persisted PID records cannot enter.
        pidfd = os.pidfd_open(process.pid, 0)
        os.set_inheritable(pidfd, False)
        directory = os.open(
            f"/proc/{process.pid}",
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        # Counter files are read only by collectors, never by the launch thread.
        # The original proc directory descriptor cannot retarget a reused PID.
        node = os.fstat(directory)
        identity = canonical_identity(
            {
                "original_observer_epoch": epoch.uri,
                "native_node": [node.st_dev, node.st_ino],
                "instance": secrets.token_hex(32),
            }
        )
        probe = _LinuxProcessProbe(directory, pidfd, identity, _issuer=_ISSUER)
        probe._require_live()
        return probe
    except BaseException:
        for fd in (directory, pidfd):
            if fd is not None:
                with suppress(OSError):
                    os.close(fd)
        raise


class OriginalProcessObservations:
    """Finite launch membership, not action admission or complete tree attribution.

    Nested children created inside a launched tool are not enumerated here. A
    receiver must join genuine live action/reservation owners and implement native
    subtree attribution before labeling any aggregate as an action measurement.
    """

    def __init__(self, *, maximum_processes=64):
        int_value(
            maximum_processes, "telemetry.native_processes", minimum=1, maximum=64
        )
        self._maximum = maximum_processes
        self._lock = threading.Lock()
        self._probes = ()
        self._closed = False
        self.registration_failed = False
        self.epoch = canonical_identity(
            {"original_process_observer": secrets.token_hex(32)}
        )

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_process_registry_not_serializable")

    def _register(self, process):
        if not self._lock.acquire(blocking=False):
            self.registration_failed = True
            return None
        try:
            self._probes = tuple(p for p in self._probes if not p.closed)
            if self._closed or len(self._probes) >= self._maximum:
                self.registration_failed = True
                return None
            probe = _capture_original_launch(process, self.epoch)
            self._probes += (probe,)
            if self._closed:
                probe.close()
                self.registration_failed = True
                return None
            return probe
        finally:
            self._lock.release()

    def active(self):
        if not self._lock.acquire(blocking=False):
            _fail("busy")
        try:
            if self._closed:
                _fail("closed")
            self._probes = tuple(p for p in self._probes if not p.closed)
            return self._probes
        finally:
            self._lock.release()

    def close(self):
        self._closed = True
        # Each probe defers descriptor release if a collector is inside a read.
        for probe in self._probes:
            probe.close()


@contextmanager
def observe_original_process_launches(*, maximum_processes=64):
    """Opt-in in the original launching thread; never reconstructs a live owner."""
    owner = OriginalProcessObservations(maximum_processes=maximum_processes)
    token = _CURRENT.set(owner)
    try:
        yield owner
    finally:
        _CURRENT.reset(token)
        owner.close()


def register_original_process_launch(process):
    """Builder hook only. Observation refusal never changes tool execution."""
    owner = _CURRENT.get()
    if owner is None:
        return None
    try:
        return owner._register(process)
    except Exception:
        owner.registration_failed = True
        return None


def retire_original_process_observation(probe):
    if probe is not None:
        probe.close()
