"""Bound failure diagnostics without replacing native gate failures."""

from __future__ import annotations

import ctypes
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.builders._process import BoundedProcessResult
from tests.support import windows_lock_observation as observation


def _set_uint(pointer, value):
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value


def _api(*, needed=1, list_code=0):
    def start(session, flags, key):
        _set_uint(session, 77)
        return 0

    def get_list(session, required, count, records, reboot):
        _set_uint(required, needed)
        if records is None:
            return 234 if needed else 0
        _set_uint(count, needed)
        if needed:
            records[0].process.pid = 1234
            records[0].process.started.low = 89
            records[0].process.started.high = 17
            records[0].application_type = 5
            records[0].application_name[0] = ord("X")
        return list_code

    return SimpleNamespace(
        RmStartSession=mock.Mock(side_effect=start),
        RmRegisterResources=mock.Mock(return_value=0),
        RmGetList=mock.Mock(side_effect=get_list),
        RmEndSession=mock.Mock(return_value=0),
    )


class WindowsLockObservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.file = self.root / "locked.log"
        self.file.write_bytes(b"fixture\n")

    def test_native_layout_and_exact_file_registration(self):
        self.assertEqual(ctypes.sizeof(observation._UniqueProcess), 12)
        self.assertEqual(ctypes.sizeof(observation._ProcessInfo), 668)
        self.assertEqual(observation._ProcessInfo.application_name.offset, 12)
        self.assertEqual(observation._ProcessInfo.application_type.offset, 652)
        api = _api()
        result = observation.observe_file_users([str(self.file)], api=api)
        self.assertEqual(result["state"], "observed")
        self.assertTrue(result["diagnostic_only"])
        self.assertEqual(result["resources"], ["locked.log"])
        self.assertEqual(
            result["users"], [{"pid": 1234, "started": (17 << 32) | 89, "kind": 5}]
        )
        arguments = api.RmRegisterResources.call_args.args
        self.assertEqual(arguments[:2], (77, 1))
        self.assertEqual(arguments[2][0], str(self.file))
        self.assertEqual(arguments[3:], (0, None, 0, None))
        self.assertIs(api.RmGetList.restype, ctypes.c_uint32)
        self.assertEqual(
            api.RmGetList.argtypes[3], ctypes.POINTER(observation._ProcessInfo)
        )
        api.RmEndSession.assert_called_once_with(77)
        self.assertNotIn("application_name", json.dumps(result))

    def test_empty_observation_is_diagnostic_not_cleanup_authority(self):
        api = _api(needed=0)
        result = observation.observe_file_users([str(self.file)], api=api)
        self.assertEqual(result["users"], [])
        self.assertEqual(result["state"], "observed")
        self.assertTrue(result["diagnostic_only"])
        self.assertEqual(api.RmGetList.call_count, 1)
        api.RmEndSession.assert_called_once_with(77)

    def test_process_limit_refuses_before_allocating_and_closes_session(self):
        api = _api(needed=33)
        result = observation.observe_file_users([str(self.file)], api=api)
        self.assertEqual(result["state"], "process_limit")
        self.assertEqual(api.RmGetList.call_count, 1)
        api.RmEndSession.assert_called_once_with(77)

    def test_changing_list_is_not_retried_or_reported_as_complete(self):
        api = _api(list_code=234)
        result = observation.observe_file_users([str(self.file)], api=api)
        self.assertEqual(result["state"], "changed_or_api_error")
        self.assertEqual(result["users"], [])
        self.assertEqual(api.RmGetList.call_count, 2)
        api.RmEndSession.assert_called_once_with(77)

    def test_start_and_registration_errors_preserve_numeric_codes(self):
        for phase in ("start", "register"):
            with self.subTest(phase=phase):
                api = _api()
                getattr(
                    api, "RmStartSession" if phase == "start" else "RmRegisterResources"
                ).side_effect = None
                getattr(
                    api, "RmStartSession" if phase == "start" else "RmRegisterResources"
                ).return_value = 5
                result = observation.observe_file_users([str(self.file)], api=api)
                self.assertEqual(
                    (result["state"], result["phase"], result["code"]),
                    ("api_error", phase, 5),
                )
                self.assertEqual(api.RmEndSession.call_count, int(phase == "register"))

    def test_registration_exception_still_ends_session(self):
        api = _api()
        api.RmRegisterResources.side_effect = OSError("fixture observation failure")
        with self.assertRaises(OSError):
            observation.observe_file_users([str(self.file)], api=api)
        api.RmEndSession.assert_called_once_with(77)

    def test_file_and_ancestor_bounds_refuse_before_native_session(self):
        api = _api()
        for paths in ([], [str(self.file)] * 5, ["relative.log"], [str(self.root)]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                observation.observe_file_users(paths, api=api)
        with mock.patch(
            "literate_ai._filesystem.require_safe_directory",
            side_effect=ValueError("fixture unsafe ancestor"),
        ):
            with self.assertRaises(ValueError):
                observation.observe_file_users([str(self.file)], api=api)
        api.RmStartSession.assert_not_called()

    def test_diagnostic_failure_preserves_exact_original_cleanup_error(self):
        original = PermissionError(32, "fixture sharing violation")
        temporary = mock.MagicMock()
        temporary.name = str(self.root)
        temporary.__enter__.return_value = str(self.root)
        temporary.__exit__.side_effect = original
        order = []
        jobs = mock.Mock()
        jobs.failure_report.side_effect = lambda: (
            order.append("jobs") or {"state": "observed"}
        )

        def files(*args):
            order.append("files")
            raise ImportError("fixture diagnostic unavailable")

        with (
            mock.patch(
                "tests.support.windows_job_observation.observe_owned_jobs",
                return_value=nullcontext(jobs),
            ),
            mock.patch.object(
                observation.tempfile, "TemporaryDirectory", return_value=temporary
            ),
            mock.patch.object(
                observation,
                "add_cleanup_observation",
                side_effect=files,
            ),
            self.assertRaises(PermissionError) as raised,
        ):
            with observation.observed_temporary_directory([], ("locked.log",)):
                pass
        self.assertIs(raised.exception, original)
        self.assertIn("ImportError", original.__notes__[0])
        self.assertEqual(order, ["jobs", "files"])
        self.assertIn("Windows owned jobs:", original.__notes__[1])

    def test_helper_is_owned_bounded_and_observation_does_not_expose_environment(self):
        error = PermissionError(32, "fixture sharing violation")
        result = BoundedProcessResult(0, b'{"state":"observed","users":[]}', b"")
        with (
            mock.patch.object(observation.sys, "platform", "win32"),
            mock.patch(
                "literate_ai.adapters.builders._process.run_bounded_process",
                return_value=result,
            ) as run,
        ):
            observation.add_cleanup_observation(
                error,
                self.root,
                ("locked.log",),
                [SimpleNamespace(pid=123, returncode=1)],
            )
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertEqual(json.loads(command[-1]), [str(self.file)])
        settings = run.call_args.kwargs
        self.assertEqual(settings["timeout_seconds"], 10)
        self.assertEqual(settings["stdout_limit_bytes"], 8192)
        self.assertEqual(settings["stderr_limit_bytes"], 1024)
        self.assertTrue(settings["terminate_descendants"])
        self.assertFalse(settings["trace"])
        note = json.loads(error.__notes__[0].split(": ", 1)[1])
        self.assertEqual(note["owned"], [{"pid": 123, "exit": 1}])
        self.assertNotIn("environment", note)

    def test_directory_only_failure_remains_explicitly_unknown(self):
        error = PermissionError(32, "fixture directory sharing violation")
        with mock.patch.object(observation.sys, "platform", "win32"):
            observation.add_cleanup_observation(error, self.root, ("absent.log",), [])
        note = json.loads(error.__notes__[0].split(": ", 1)[1])
        self.assertEqual(note["observation"]["directory_holders"], "unknown")
