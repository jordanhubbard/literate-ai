"""Read-only native process identities captured at actual framework spawn.

There is no public PID selector or decoded-handle constructor. A token describes
one observed kernel process generation; it carries no Popen, signal, cancellation
or execution-owner handle. Unsupported native backends remain unavailable.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from dataclasses import dataclass, field

from .worker_telemetry_issuance import ObservationIssuance

_PROCESS_SEAL = object()
_MAX_PROC_BYTES = 16 * 1024


class ProcessObservationUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("worker_telemetry.process_unavailable")


def _proc_bytes(pid: int, name: str) -> bytes:
    # Both components originate in this module, never observation wire values.
    if type(pid) is not int or not 1 <= pid <= 2**31 - 1:
        raise ProcessObservationUnavailable()
    if name != "stat":
        raise ProcessObservationUnavailable()
    descriptor = os.open(
        f"/proc/{pid}/{name}",
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ProcessObservationUnavailable()
        result = bytearray()
        while len(result) <= _MAX_PROC_BYTES:
            block = os.read(descriptor, min(4096, _MAX_PROC_BYTES + 1 - len(result)))
            if not block:
                break
            result.extend(block)
        if len(result) > _MAX_PROC_BYTES:
            raise ProcessObservationUnavailable()
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ProcessObservationUnavailable()
        return bytes(result)
    finally:
        os.close(descriptor)


def _linux_stat(pid: int) -> tuple[int, int, int, int, int]:
    raw = _proc_bytes(pid, "stat")
    # comm can contain spaces or ')'; it is neither returned nor retained.
    boundary = raw.rfind(b")")
    if boundary < 0:
        raise ProcessObservationUnavailable()
    prefix = raw[: raw.find(b" ")]
    parts = raw[boundary + 2 :].split()
    if prefix != str(pid).encode("ascii") or len(parts) < 22:
        raise ProcessObservationUnavailable()
    parent, group, start = (int(parts[index]) for index in (1, 2, 19))
    cpu_ticks = int(parts[11]) + int(parts[12])
    resident_pages = int(parts[21])
    if min(parent, group, start, cpu_ticks, resident_pages) < 0:
        raise ProcessObservationUnavailable()
    return parent, group, start, cpu_ticks, resident_pages


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class SpawnedProcessObservation:
    """Private readonly generation identity, not a serializable authority grant."""

    _pid: int
    _parent: int
    _group: int
    _start: int
    _boot_epoch: str
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self._seal) is not ObservationIssuance:
            raise ProcessObservationUnavailable()
        self._seal.require_constructor(self, _PROCESS_SEAL)

    def __reduce__(self):
        raise TypeError("native process observation tokens cannot be restored")

    @property
    def epoch(self) -> str:
        value = (
            f"linux-process:{self._boot_epoch}:{self._pid}:{self._parent}:"
            f"{self._group}:{self._start}"
        )
        return hashlib.sha256(value.encode("ascii")).hexdigest()

    def require_current(self) -> None:
        if type(self._seal) is not ObservationIssuance:
            raise ProcessObservationUnavailable()
        self._seal.require_original(self, _PROCESS_SEAL)
        parent, group, start, _, _ = _linux_stat(self._pid)
        if (parent, group, start) != (self._parent, self._group, self._start):
            raise ProcessObservationUnavailable()

    def cpu_and_resident_bytes(self) -> tuple[int, int]:
        self.require_current()
        before = _linux_stat(self._pid)
        if before[:3] != (self._parent, self._group, self._start):
            raise ProcessObservationUnavailable()
        ticks_per_second = os.sysconf("SC_CLK_TCK")
        page_bytes = os.sysconf("SC_PAGE_SIZE")
        if not 1 <= ticks_per_second <= 1_000_000 or not 1 <= page_bytes <= 1024**2:
            raise ProcessObservationUnavailable()
        self.require_current()
        cpu_ns = before[3] * 1_000_000_000 // ticks_per_second
        resident = before[4] * page_bytes
        if cpu_ns > 2**63 - 1 or resident > 2**63 - 1:
            raise ProcessObservationUnavailable()
        return cpu_ns, resident


def capture_spawned_process(pid: int) -> SpawnedProcessObservation | None:
    """Called only after the canonical runner actually spawned/bound its child.

    Unsupported or already-ended processes produce no token. The runner's
    control/cleanup behavior must never depend on observation availability.
    Measurements describe this process only, not an unproved complete subtree.
    """
    if sys.platform != "linux":
        return None
    try:
        parent, group, start, _, _ = _linux_stat(pid)
        # The canonical POSIX runner creates a private process group/session.
        if parent != os.getpid() or group != pid:
            return None
        descriptor = os.open(
            "/proc/sys/kernel/random/boot_id",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        )
        try:
            boot = os.read(descriptor, 65)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode) or not re.fullmatch(
                rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\n?",
                boot,
            ):
                return None
        finally:
            os.close(descriptor)
        issuance = ObservationIssuance(_PROCESS_SEAL)
        token = SpawnedProcessObservation(
            pid, parent, group, start, hashlib.sha256(boot).hexdigest(), issuance
        )
        issuance.bind(token, _PROCESS_SEAL)
        token.require_current()
        return token
    except (OSError, ValueError, OverflowError):
        return None
