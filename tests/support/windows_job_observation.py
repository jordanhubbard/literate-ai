"""Fixed-size observations of jobs already owned by one Windows fixture.

This is diagnostic evidence, never a completion oracle. No process handle is
retained across assignment/termination/close or the original cleanup boundary.
"""

from __future__ import annotations

import ctypes
import sys
import time
import weakref
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

_MAX_JOBS = 4
_MAX_EVENTS = 12
_MAX_MEMBERS = 4
_MAX_IDENTITIES = 8


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("total_user", ctypes.c_int64),
        ("total_kernel", ctypes.c_int64),
        ("period_user", ctypes.c_int64),
        ("period_kernel", ctypes.c_int64),
        ("page_faults", ctypes.c_uint32),
        ("total_processes", ctypes.c_uint32),
        ("active_processes", ctypes.c_uint32),
        ("terminated_processes", ctypes.c_uint32),
    ]


class _Members(ctypes.Structure):
    _fields_ = [
        ("assigned", ctypes.c_uint32),
        ("returned", ctypes.c_uint32),
        ("pids", ctypes.c_size_t * _MAX_MEMBERS),
    ]


def _configure(api):
    handle, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    pointer = ctypes.POINTER
    signatures = {
        "QueryInformationJobObject": (
            boolean,
            [handle, ctypes.c_int32, ctypes.c_void_p, dword, pointer(dword)],
        ),
        "OpenProcess": (handle, [dword, boolean, dword]),
        "GetProcessTimes": (boolean, [handle, *([pointer(_FileTime)] * 4)]),
        "IsProcessInJob": (boolean, [handle, handle, pointer(boolean)]),
        "WaitForSingleObject": (dword, [handle, dword]),
        "CloseHandle": (boolean, [handle]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(api, name)
        function.restype, function.argtypes = result, arguments


class JobObservations:
    def __init__(self, api, *, get_error, set_error, clock=time.monotonic):
        _configure(api)
        self.api, self.get_error, self.set_error = api, get_error, set_error
        self.clock = clock
        self.jobs = weakref.WeakKeyDictionary()
        self.job_count = 0
        self.events = []
        self.identities = set()
        self.capped = False

    def _process(self, pid, *, job=None, expected_start=None):
        row = {"pid": pid}
        if not 0 < pid <= 0xFFFFFFFF:
            return {**row, "state": "pid_out_of_range"}
        # Query and synchronization only; never request termination/VM access.
        handle = self.api.OpenProcess(0x00101000, 0, pid)
        if not handle:
            return {**row, "state": "open_unavailable", "error": self.get_error()}
        try:
            times = [_FileTime() for _ in range(4)]
            if not self.api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return {**row, "state": "times_unavailable", "error": self.get_error()}
            started = (times[0].high << 32) | times[0].low
            if not started or (
                expected_start is not None and started != expected_start
            ):
                return {**row, "state": "identity_changed"}
            row["started"] = started
            if job is not None:
                member = ctypes.c_int32()
                if not self.api.IsProcessInJob(handle, job, ctypes.byref(member)):
                    return {
                        **row,
                        "state": "membership_unavailable",
                        "error": self.get_error(),
                    }
                if not member.value:
                    return {**row, "state": "not_a_member"}
            wait = self.api.WaitForSingleObject(handle, 0)
            if wait not in (0, 258):
                return {**row, "state": "wait_unavailable", "error": self.get_error()}
            return {**row, "state": "signaled" if wait == 0 else "not_signaled"}
        finally:
            if not self.api.CloseHandle(handle):
                raise OSError("diagnostic handle close failed")

    def _snapshot(self, handle):
        if not handle:
            # NULL means the caller's ambient job to Win32; never query it.
            return {"state": "no_owned_handle"}
        deadline = self.clock() + 0.1
        accounting = _Accounting()
        length = ctypes.c_uint32()
        if not self.api.QueryInformationJobObject(
            handle,
            1,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            ctypes.byref(length),
        ):
            return {"state": "accounting_unavailable", "error": self.get_error()}
        if length.value != ctypes.sizeof(accounting):
            return {"state": "accounting_size_unknown"}
        result = {
            "state": "observed",
            "active_count_diagnostic_only": accounting.active_processes,
            "total": accounting.total_processes,
            "terminated": accounting.terminated_processes,
        }
        if self.clock() >= deadline:
            return {**result, "members_state": "observation_budget"}
        members = _Members()
        length.value = 0
        if not self.api.QueryInformationJobObject(
            handle,
            3,
            ctypes.byref(members),
            ctypes.sizeof(members),
            ctypes.byref(length),
        ):
            return {
                **result,
                "members_state": "query_unavailable",
                "error": self.get_error(),
            }
        required = _Members.pids.offset + members.returned * ctypes.sizeof(
            ctypes.c_size_t
        )
        if (
            members.assigned > _MAX_MEMBERS
            or members.returned > _MAX_MEMBERS
            or members.returned != members.assigned
            or not required <= length.value <= ctypes.sizeof(members)
        ):
            return {**result, "members_state": "capacity_or_size_unknown"}
        rows = []
        for index in range(members.returned):
            if self.clock() >= deadline:
                return {
                    **result,
                    "members_state": "observation_budget",
                    "members": rows,
                }
            row = self._process(int(members.pids[index]), job=handle)
            rows.append(row)
            if row["state"] in {"signaled", "not_signaled"}:
                identity = row["pid"], row["started"]
                if len(self.identities) < _MAX_IDENTITIES:
                    self.identities.add(identity)
                elif identity not in self.identities:
                    self.capped = True
        return {**result, "members_state": "observed", "members": rows}

    def capture(self, job, phase, *, pid=None, result=None):
        previous_error = self.get_error()
        try:
            if job not in self.jobs:
                if self.job_count >= _MAX_JOBS:
                    self.capped = True
                    return
                self.job_count += 1
                self.jobs[job] = self.job_count
            if len(self.events) >= _MAX_EVENTS:
                self.capped = True
                return
            event = {"job": self.jobs[job], "phase": phase}
            if pid is not None:
                event["root_pid"] = pid
            if result is not None:
                event["returned"] = bool(result)
                if not result:
                    event["last_error_observed"] = previous_error
            # Each snapshot is bounded in calls/buffers, not a hard deadline for
            # an individual kernel syscall. No polling or nonzero wait occurs.
            try:
                event["snapshot"] = self._snapshot(job._handle)
            except Exception as error:
                event["snapshot"] = {
                    "state": "unavailable",
                    "error_type": type(error).__name__[:48],
                }
            self.events.append(event)
        finally:
            self.set_error(previous_error)

    def failure_report(self):
        previous_error = self.get_error()
        try:
            current = []
            deadline = self.clock() + 0.1
            for pid, started in sorted(self.identities):
                if self.clock() >= deadline:
                    self.capped = True
                    break
                try:
                    row = self._process(pid, expected_start=started)
                except Exception as error:
                    row = {
                        "pid": pid,
                        "state": "unavailable",
                        "error_type": type(error).__name__[:48],
                    }
                current.append(row)
            return {
                "state": "observed",
                "diagnostic_only": True,
                "capped": self.capped,
                "events": self.events,
                "at_failure": current,
            }
        finally:
            self.set_error(previous_error)


class _Unavailable:
    def __init__(self, error):
        self.error_type = type(error).__name__[:48]

    def failure_report(self):
        return {
            "diagnostic_only": True,
            "state": "setup_unavailable",
            "error_type": self.error_type,
        }


@contextmanager
def observe_owned_jobs(*, enabled=None, api=None, job_class=None):
    if enabled is None:
        enabled = sys.platform == "win32"
    if not enabled:
        yield None
        return
    stack = ExitStack()
    try:
        try:
            from literate_ai.adapters._processes import WindowsProcessTreeJob

            if api is None:
                api = ctypes.WinDLL("kernel32.dll", winmode=0x800, use_last_error=True)
            get_error = getattr(ctypes, "get_last_error", lambda: 0)
            set_error = getattr(ctypes, "set_last_error", lambda value: None)
            observations = JobObservations(
                api, get_error=get_error, set_error=set_error
            )
            selected = WindowsProcessTreeJob if job_class is None else job_class
            assign, terminate, close = (
                selected.assign,
                selected.terminate,
                selected.close,
            )

            def capture(job, phase, **values):
                try:
                    observations.capture(job, phase, **values)
                except Exception:
                    observations.capped = True

            def assigned(job, pid):
                returned = assign(job, pid)
                capture(job, "assigned", pid=pid, result=returned)
                return returned

            def terminated(job):
                capture(job, "before_terminate")
                returned = terminate(job)
                capture(job, "after_terminate", result=returned)
                return returned

            def closed(job):
                if not job._closed:
                    capture(job, "before_close")
                return close(job)

            for name, function in (
                ("assign", assigned),
                ("terminate", terminated),
                ("close", closed),
            ):
                stack.enter_context(patch.object(selected, name, function))
        except Exception as error:
            stack.close()
            observations = _Unavailable(error)
        yield observations
    finally:
        stack.close()
