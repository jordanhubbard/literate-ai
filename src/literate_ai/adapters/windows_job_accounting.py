"""Numeric accounting for an original runner-owned Windows Job.

This module does not mint ownership or admit observations. Its future caller
must hold the original Job lifetime on the runner thread throughout this call.
The returned integers describe actual associated Job members, including exited
members; they do not prove a complete pre-assignment process subtree.
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import Any


class JobAccountingUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("worker_telemetry.windows_job_accounting_unavailable")


class _BasicAccounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


@dataclass(frozen=True, slots=True)
class JobAccounting:
    """Comparison facts only: no handles, PIDs, paths or live authority."""

    started_monotonic_ns: int
    ended_monotonic_ns: int
    observed_at_ms: int
    cpu_time_ns: int
    total_processes: int
    active_processes: int


def read_original_job_accounting(kernel32: Any, handle: int) -> JobAccounting:
    """Perform one fixed-size native query while the caller owns the Job.

    No lock, thread, retry, handle duplication or observer callback occurs here.
    The call must never run against a saved numeric handle after owner release.
    Query cost is not a hard real-time guarantee. The caller treats ANY failure
    as unavailable and must not change execution/cleanup based on this function.
    """

    if type(handle) is not int or handle <= 0:
        raise JobAccountingUnavailable()
    query = kernel32.QueryInformationJobObject
    # These are isolated query-function signatures; do not mutate the canonical
    # Create/Assign/Terminate functions or their execution semantics here.
    query.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    query.restype = ctypes.c_int
    information = _BasicAccounting()
    returned = ctypes.c_uint32()
    started = time.monotonic_ns()
    if not query(
        ctypes.c_void_p(handle),
        1,  # JobObjectBasicAccountingInformation
        ctypes.byref(information),
        ctypes.sizeof(information),
        ctypes.byref(returned),
    ):
        raise JobAccountingUnavailable()
    ended = time.monotonic_ns()
    observed_at_ms = time.time_ns() // 1_000_000
    user = int(information.TotalUserTime)
    kernel = int(information.TotalKernelTime)
    total = int(information.TotalProcesses)
    active = int(information.ActiveProcesses)
    cpu = (user + kernel) * 100  # Native units are 100-nanosecond ticks.
    if (
        returned.value != ctypes.sizeof(information)
        or min(user, kernel, started) < 0
        or not started <= ended <= 2**63 - 1
        or not 0 <= cpu <= 2**63 - 1
        or not 0 <= observed_at_ms <= 2**63 - 1
        or active > total
    ):
        raise JobAccountingUnavailable()
    return JobAccounting(started, ended, observed_at_ms, cpu, total, active)
