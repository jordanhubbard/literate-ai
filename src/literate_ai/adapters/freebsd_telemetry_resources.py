"""Comparison-only reader for bounded native FreeBSD resource observations.

This does not launch/provision a helper or create a live owner. Its caller must
still prove original runner, private channel, generation, deadline and freshness
before AND after observation. Numeric rows never confer PID/control authority.
The C producer uses native headers, not guessed kinfo_proc ABI offsets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .worker_telemetry_wire import WorkerTelemetryWireError

MAX_NATIVE_RESOURCE_BYTES = 96 * 1024
MAX_NATIVE_RESOURCE_MEMBERS = 128
_MAX_INTEGER = (1 << 63) - 1
_SCHEMA = "literate-ai/native-freebsd-resource-snapshot@1"
_ROW_FIELDS = frozenset(
    (
        "pid",
        "parent_pid",
        "reaper_pid",
        "flags",
        "start_seconds",
        "start_microseconds",
        "cpu_self_ns",
        "cpu_children_ns",
        "resident_bytes",
    )
)
_ROOT_FIELDS = frozenset(
    (
        "schema",
        "status",
        "capture_started_monotonic_ns",
        "monotonic_ns",
        "observed_at_ms",
        "cpu_time_ns",
        "memory_resident_bytes",
        "members",
    )
)


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_observation_unavailable")


def _integer(value, minimum=0, maximum=_MAX_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        _refuse()
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _refuse()
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class FreeBsdResourceMember:
    """Untrusted-by-itself numeric facts, not an execution witness."""

    pid: int
    parent_pid: int
    reaper_pid: int
    flags: int
    start_seconds: int
    start_microseconds: int
    cpu_self_ns: int
    cpu_children_ns: int
    resident_bytes: int


@dataclass(frozen=True, slots=True)
class FreeBsdResourceSnapshot:
    capture_started_monotonic_ns: int
    monotonic_ns: int
    observed_at_ms: int
    cpu_time_ns: int
    memory_resident_bytes: int
    members: tuple[FreeBsdResourceMember, ...]


def compare_native_resource_snapshot(
    raw: bytes, *, root_generation: tuple[int, int, int], original_parent_pid: int
) -> FreeBsdResourceSnapshot:
    """Decode and compare to caller-selected facts, never establish those facts.

    root_generation is (PID, native start seconds, native start microseconds),
    obtained by the ORIGINAL live runner, not a historical descriptor. RSS sums
    current resident pages over processes, so shared pages may count repeatedly.
    CPU sums own runtime and already-reaped-child runtime at disjoint live
    frontiers. Neither number is a host counter, peak RSS or a disk byte count.
    """
    if (
        type(raw) is not bytes
        or not 1 <= len(raw) <= MAX_NATIVE_RESOURCE_BYTES
        or type(root_generation) is not tuple
        or len(root_generation) != 3
    ):
        _refuse()
    expected_pid = _integer(root_generation[0], 2, (1 << 31) - 1)
    expected_seconds = _integer(root_generation[1], 1)
    expected_microseconds = _integer(root_generation[2], 0, 999_999)
    _integer(original_parent_pid, 2, (1 << 31) - 1)
    try:
        document = json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError):
        _refuse()
    if (
        type(document) is not dict
        or document.keys() != _ROOT_FIELDS
        or document["schema"] != _SCHEMA
        or document["status"] != "ok"
    ):
        _refuse()
    started = _integer(document["capture_started_monotonic_ns"], 1)
    finished = _integer(document["monotonic_ns"], 1)
    if not started <= finished < started + 2_000_000_000:
        _refuse()
    observed = _integer(document["observed_at_ms"], 1)
    cpu = _integer(document["cpu_time_ns"])
    rss = _integer(document["memory_resident_bytes"])
    rows = document["members"]
    if type(rows) is not list or not 1 <= len(rows) <= MAX_NATIVE_RESOURCE_MEMBERS:
        _refuse()
    # Validate ALL raw rows/counts/sums/lineage before constructing any DTO.
    by_pid = {}
    actual_cpu = actual_rss = 0
    for row in rows:
        if type(row) is not dict or row.keys() != _ROW_FIELDS:
            _refuse()
        pid = _integer(row["pid"], 2, (1 << 31) - 1)
        if pid in by_pid:
            _refuse()
        _integer(row["parent_pid"], 1, (1 << 31) - 1)
        _integer(row["reaper_pid"], 2, (1 << 31) - 1)
        flags = _integer(row["flags"], 1, 7)
        if not flags & 1:
            _refuse()
        _integer(row["start_seconds"], 1)
        _integer(row["start_microseconds"], 0, 999_999)
        actual_cpu += _integer(row["cpu_self_ns"]) + _integer(row["cpu_children_ns"])
        actual_rss += _integer(row["resident_bytes"])
        if max(actual_cpu, actual_rss) > _MAX_INTEGER:
            _refuse()
        by_pid[pid] = row
    root = rows[0]
    if (
        (root["pid"], root["start_seconds"], root["start_microseconds"])
        != (expected_pid, expected_seconds, expected_microseconds)
        or root["parent_pid"] != original_parent_pid
        or root["reaper_pid"] != expected_pid
        or root["flags"] != 5
        or actual_cpu != cpu
        or actual_rss != rss
    ):
        _refuse()
    for row in rows[1:]:
        reaper = by_pid.get(row["reaper_pid"])
        if reaper is None or not reaper["flags"] & 4:
            _refuse()
        cursor = row
        seen = set()
        saw_reaper = False
        while cursor["pid"] != expected_pid:
            if cursor["pid"] in seen:
                _refuse()
            seen.add(cursor["pid"])
            cursor = by_pid.get(cursor["parent_pid"])
            if cursor is None:
                _refuse()
            saw_reaper |= cursor["pid"] == row["reaper_pid"]
        if not saw_reaper:
            _refuse()
    return FreeBsdResourceSnapshot(
        started,
        finished,
        observed,
        cpu,
        rss,
        tuple(FreeBsdResourceMember(**row) for row in rows),
    )
