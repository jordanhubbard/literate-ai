"""Failure-only observations for exact Windows gate fixture resources.

This reports Restart Manager observations; an empty result does not prove that
kernel, transient or otherwise unreported holders have released a resource.
It never shuts down/restarts applications or changes the original test result.
"""

from __future__ import annotations

import ctypes
import json
import os
import stat
import sys
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path

_MAX_FILES = 4
_MAX_PROCESSES = 32
_MORE_DATA = 234


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _UniqueProcess(ctypes.Structure):
    _fields_ = [("pid", ctypes.c_uint32), ("started", _FileTime)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", _UniqueProcess),
        ("application_name", ctypes.c_uint16 * 256),
        ("service_name", ctypes.c_uint16 * 64),
        ("application_type", ctypes.c_int32),
        ("application_status", ctypes.c_uint32),
        ("session_id", ctypes.c_uint32),
        ("restartable", ctypes.c_int32),
    ]


def _bind(api):
    uint = ctypes.c_uint32
    pointer_uint = ctypes.POINTER(uint)
    signatures = {
        "RmStartSession": [pointer_uint, uint, ctypes.POINTER(ctypes.c_uint16)],
        "RmRegisterResources": [
            uint,
            uint,
            ctypes.POINTER(ctypes.c_wchar_p),
            uint,
            ctypes.POINTER(_UniqueProcess),
            uint,
            ctypes.POINTER(ctypes.c_wchar_p),
        ],
        "RmGetList": [
            uint,
            pointer_uint,
            pointer_uint,
            ctypes.POINTER(_ProcessInfo),
            pointer_uint,
        ],
        "RmEndSession": [uint],
    }
    for name, arguments in signatures.items():
        function = getattr(api, name)
        function.argtypes = arguments
        function.restype = uint


def observe_file_users(filenames, *, api=None):
    """Inspect at most four exact regular file paths and 32 reported holders."""
    from literate_ai._filesystem import require_safe_directory

    if not 1 <= len(filenames) <= _MAX_FILES:
        raise ValueError("diagnostic requires one to four exact files")
    paths = []
    for name in filenames:
        if not isinstance(name, str) or "\0" in name or len(name) > 1024:
            raise ValueError("invalid diagnostic path")
        path = Path(name)
        if not path.is_absolute() or len(path.name) > 64:
            raise ValueError("diagnostic path must be absolute with a short filename")
        require_safe_directory(path.parent)
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("diagnostic requires regular non-reparse files")
        paths.append(str(path))
    result = {
        "schema": "literate-ai/windows-gate-resource-observation@1",
        "diagnostic_only": True,
        "resources": [Path(path).name for path in paths],
        "state": "unknown",
        "users": [],
    }
    if api is None:
        if sys.platform != "win32":
            result["state"] = "unsupported_platform"
            return result
        api = ctypes.WinDLL("Rstrtmgr.dll", winmode=0x800, use_last_error=True)
    _bind(api)
    session = ctypes.c_uint32()
    key = (ctypes.c_uint16 * 33)()
    code = api.RmStartSession(ctypes.byref(session), 0, key)
    if code:
        result.update(state="api_error", phase="start", code=int(code))
        return result
    try:
        names = (ctypes.c_wchar_p * len(paths))(*paths)
        code = api.RmRegisterResources(
            session.value, len(paths), names, 0, None, 0, None
        )
        if code:
            result.update(state="api_error", phase="register", code=int(code))
            return result
        needed, count, reboot = ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32()
        code = api.RmGetList(
            session.value,
            ctypes.byref(needed),
            ctypes.byref(count),
            None,
            ctypes.byref(reboot),
        )
        if code not in (0, _MORE_DATA):
            result.update(state="api_error", phase="size", code=int(code))
            return result
        if needed.value > _MAX_PROCESSES:
            result.update(state="process_limit", needed=needed.value)
            return result
        if code == 0 and needed.value == 0:
            result["state"] = "observed"
            return result
        if code != _MORE_DATA or needed.value == 0:
            result["state"] = "inconsistent_size"
            return result
        capacity = needed.value
        records = (_ProcessInfo * capacity)()
        count.value = capacity
        code = api.RmGetList(
            session.value,
            ctypes.byref(needed),
            ctypes.byref(count),
            records,
            ctypes.byref(reboot),
        )
        if code or count.value > capacity or needed.value > capacity:
            result.update(state="changed_or_api_error", phase="list", code=int(code))
            return result
        result["users"] = [
            {
                "pid": records[index].process.pid,
                "started": (records[index].process.started.high << 32)
                | records[index].process.started.low,
                "kind": records[index].application_type,
            }
            for index in range(count.value)
        ]
        result["state"] = "observed"
        return result
    finally:
        code = api.RmEndSession(session.value)
        if code:
            result["session_close_code"] = int(code)


def add_cleanup_observation(error, root, names, processes):
    """Enrich an original failure without replacing it or changing cleanup."""
    if sys.platform != "win32":
        return
    from literate_ai.adapters.builders._process import run_bounded_process

    context = {
        "parent_pid": os.getpid(),
        "owned": [
            {"pid": process.pid, "exit": process.returncode}
            for process in processes[:16]
        ],
    }
    try:
        files = [str(root / name) for name in names if (root / name).is_file()]
        if not files:
            context["observation"] = {
                "state": "no_remaining_named_files",
                "directory_holders": "unknown",
            }
        else:
            observed = run_bounded_process(
                [sys.executable, str(Path(__file__).resolve()), json.dumps(files)],
                cwd=Path(__file__).resolve().parents[2],
                environment=dict(os.environ),
                timeout_seconds=10,
                stdout_limit_bytes=8192,
                stderr_limit_bytes=1024,
                error_prefix="test.cleanup_observation",
                terminate_descendants=True,
                trace=False,
            )
            if observed.returncode:
                context["observation"] = {
                    "state": "helper_failed",
                    "exit": observed.returncode,
                }
            else:
                context["observation"] = json.loads(observed.stdout)
    except Exception as diagnostic_error:
        context["observation"] = {
            "state": "diagnostic_unavailable",
            "error_type": type(diagnostic_error).__name__,
        }
        code = getattr(diagnostic_error, "code", None)
        if isinstance(code, str) and code.startswith("test.cleanup_observation"):
            context["observation"]["code"] = code[:80]
    error.add_note("Windows fixture resources: " + json.dumps(context, sort_keys=True))


@contextmanager
def observed_temporary_directory(processes, names):
    temporary = tempfile.TemporaryDirectory()
    collector = nullcontext(None)
    try:
        from tests.support.windows_job_observation import observe_owned_jobs

        collector = observe_owned_jobs()
    except Exception:
        pass
    jobs = None
    try:
        with collector as jobs:
            with temporary as directory:
                yield directory
    except OSError as error:
        # Hooks are removed before observing the original cleanup boundary or
        # launching the separate Restart Manager diagnostic child.
        if jobs is not None:
            try:
                error.add_note(
                    "Windows owned jobs: "
                    + json.dumps(
                        jobs.failure_report(), sort_keys=True, separators=(",", ":")
                    )
                )
            except Exception as diagnostic_error:
                error.add_note(
                    "Windows owned jobs unavailable: " + type(diagnostic_error).__name__
                )
        try:
            add_cleanup_observation(error, Path(temporary.name), names, processes)
        except Exception as diagnostic_error:
            error.add_note(
                "Windows fixture diagnostic unavailable: "
                + type(diagnostic_error).__name__
            )
        raise


if __name__ == "__main__":
    try:
        value = json.loads(sys.argv[1])
        if not isinstance(value, list):
            raise ValueError("file list required")
        report = observe_file_users(value)
    except Exception as error:
        report = {"state": "diagnostic_unavailable", "error_type": type(error).__name__}
    print(json.dumps(report, sort_keys=True))
