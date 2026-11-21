"""Bounded job diagnostics preserve termination and original fixture failures."""

import ctypes
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support import windows_job_observation as observation


def _uint(pointer, value):
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value


def _api(*, pids=(111,), wait=0, member=True):
    starts = {pid: (1 << 32) + pid for pid in pids}

    def query(job, kind, output, capacity, length):
        if kind == 1:
            value = ctypes.cast(output, ctypes.POINTER(observation._Accounting))[0]
            value.active_processes = 4
            value.total_processes = 5
            value.terminated_processes = 1
            _uint(length, ctypes.sizeof(observation._Accounting))
        else:
            value = ctypes.cast(output, ctypes.POINTER(observation._Members))[0]
            value.assigned = value.returned = len(pids)
            for index, pid in enumerate(pids[: observation._MAX_MEMBERS]):
                value.pids[index] = pid
            _uint(length, ctypes.sizeof(observation._Members))
        return 1

    def times(handle, created, *unused):
        value = ctypes.cast(created, ctypes.POINTER(observation._FileTime))[0]
        started = starts[handle - 9000]
        value.low = started & 0xFFFFFFFF
        value.high = started >> 32
        return 1

    def membership(process, job, result):
        ctypes.cast(result, ctypes.POINTER(ctypes.c_int32))[0] = int(member)
        return 1

    return SimpleNamespace(
        QueryInformationJobObject=Mock(side_effect=query),
        OpenProcess=Mock(side_effect=lambda rights, inherit, pid: pid + 9000),
        GetProcessTimes=Mock(side_effect=times),
        IsProcessInJob=Mock(side_effect=membership),
        WaitForSingleObject=Mock(return_value=wait),
        CloseHandle=Mock(return_value=1),
        starts=starts,
    )


class _Job:
    def __init__(self, handle=93):
        self._handle, self._closed = handle, False
        self.calls = []

    def assign(self, pid):
        self.calls.append(("assign", pid))
        return True

    def terminate(self):
        self.calls.append(("terminate",))
        return False

    def close(self):
        self.calls.append(("close",))
        self._closed = True


class WindowsJobObservationTests(unittest.TestCase):
    def observer(self, api=None, **kwargs):
        return observation.JobObservations(
            api or _api(), get_error=lambda: 17, set_error=lambda value: None, **kwargs
        )

    def test_native_layout_and_signaled_member_despite_positive_active_count(self):
        api = _api()
        observed = self.observer(api)
        job = _Job()
        observed.capture(job, "before_close")
        snapshot = observed.events[0]["snapshot"]
        self.assertEqual(ctypes.sizeof(observation._Accounting), 48)
        self.assertEqual(observation._Accounting.active_processes.offset, 40)
        self.assertEqual(observation._Members.pids.offset, 8)
        self.assertEqual(snapshot["active_count_diagnostic_only"], 4)
        self.assertEqual(snapshot["members"][0]["state"], "signaled")
        self.assertEqual(snapshot["members"][0]["started"], (1 << 32) + 111)
        api.OpenProcess.assert_called_once_with(0x101000, 0, 111)
        api.IsProcessInJob.assert_called_once()
        self.assertEqual(api.IsProcessInJob.call_args.args[1], 93)
        api.WaitForSingleObject.assert_called_once_with(9111, 0)
        api.CloseHandle.assert_called_once_with(9111)
        self.assertIs(api.OpenProcess.restype, ctypes.c_void_p)
        self.assertIs(api.WaitForSingleObject.restype, ctypes.c_uint32)
        self.assertNotIn("command", json.dumps(observed.failure_report()))

    def test_failure_recheck_requires_same_creation_identity_before_wait(self):
        api = _api(wait=258)
        observed = self.observer(api)
        observed.capture(_Job(), "before_close")
        self.assertEqual(
            observed.events[0]["snapshot"]["members"][0]["state"], "not_signaled"
        )
        same = observed.failure_report()["at_failure"]
        self.assertEqual(
            same, [{"pid": 111, "started": (1 << 32) + 111, "state": "not_signaled"}]
        )
        self.assertEqual(api.CloseHandle.call_count, 2)
        api.starts[111] += 1
        api.WaitForSingleObject.reset_mock()
        result = observed.failure_report()["at_failure"]
        self.assertEqual(result, [{"pid": 111, "state": "identity_changed"}])
        api.WaitForSingleObject.assert_not_called()
        self.assertEqual(api.CloseHandle.call_count, 3)

    def test_nonmember_or_failed_time_query_never_gets_a_liveness_claim(self):
        for failed_times in (False, True):
            with self.subTest(failed_times=failed_times):
                api = _api(member=False)
                if failed_times:
                    api.GetProcessTimes.side_effect = None
                    api.GetProcessTimes.return_value = 0
                observed = self.observer(api)
                observed.capture(_Job(), "before_close")
                state = observed.events[0]["snapshot"]["members"][0]["state"]
                self.assertEqual(
                    state, "times_unavailable" if failed_times else "not_a_member"
                )
                self.assertEqual(observed.identities, set())
                api.WaitForSingleObject.assert_not_called()
                api.CloseHandle.assert_called_once_with(9111)

    def test_fixed_capacity_refuses_without_resize_or_member_open(self):
        api = _api(pids=tuple(range(1, 6)))
        observed = self.observer(api)
        observed.capture(_Job(), "before_close")
        self.assertEqual(
            observed.events[0]["snapshot"]["members_state"], "capacity_or_size_unknown"
        )
        self.assertEqual(api.QueryInformationJobObject.call_count, 2)
        api.OpenProcess.assert_not_called()

    def test_null_handle_never_queries_the_ambient_job(self):
        api = _api()
        observed = self.observer(api)
        observed.capture(_Job(handle=0), "before_close")
        self.assertEqual(observed.events[0]["snapshot"]["state"], "no_owned_handle")
        api.QueryInformationJobObject.assert_not_called()

    def test_api_error_and_close_error_stay_diagnostic_and_restore_last_error(self):
        api = _api()
        native_error = [17]

        def broken(*args):
            native_error[0] = 991
            raise OSError("query failed")

        api.QueryInformationJobObject.side_effect = broken
        observed = observation.JobObservations(
            api,
            get_error=lambda: native_error[0],
            set_error=lambda value: native_error.__setitem__(0, value),
        )
        observed.capture(_Job(), "before_close")
        self.assertEqual(native_error[0], 17)
        self.assertEqual(observed.events[0]["snapshot"]["state"], "unavailable")
        api = _api()
        api.CloseHandle.return_value = 0
        observed = self.observer(api)
        observed.capture(_Job(), "before_close")
        self.assertEqual(observed.events[0]["snapshot"]["state"], "unavailable")
        self.assertEqual(observed.identities, set())
        api.CloseHandle.assert_called_once_with(9111)

    def test_event_and_job_caps_hold_without_retaining_job_objects(self):
        observed = self.observer()
        for _ in range(20):
            observed.capture(_Job(), "assigned", pid=111, result=True)
        self.assertTrue(observed.capped)
        self.assertEqual(len(observed.events), observation._MAX_JOBS)
        self.assertEqual(len(observed.jobs), 0)
        observed = self.observer()
        job = _Job()
        for _ in range(20):
            observed.capture(job, "before_close")
        self.assertEqual(len(observed.events), observation._MAX_EVENTS)
        self.assertTrue(observed.capped)

    def test_budget_stops_further_queries_without_waiting(self):
        api = _api()
        observed = self.observer(api, clock=Mock(side_effect=[0, 1]))
        observed.capture(_Job(), "before_close")
        self.assertEqual(
            observed.events[0]["snapshot"]["members_state"], "observation_budget"
        )
        self.assertEqual(api.QueryInformationJobObject.call_count, 1)
        api.OpenProcess.assert_not_called()

    def test_hooks_preserve_methods_exceptions_and_restore_original_class(self):
        api = _api()
        original = _Job.terminate
        error = OSError("original fixture cleanup")
        with self.assertRaises(OSError) as raised:
            with observation.observe_owned_jobs(
                enabled=True, api=api, job_class=_Job
            ) as observed:
                job = _Job()
                self.assertTrue(job.assign(111))
                self.assertFalse(job.terminate())
                job.close()
                self.assertEqual(
                    job.calls, [("assign", 111), ("terminate",), ("close",)]
                )
                raise error
        self.assertIs(raised.exception, error)
        self.assertIs(_Job.terminate, original)
        self.assertEqual(
            [row["phase"] for row in observed.events],
            ["assigned", "before_terminate", "after_terminate", "before_close"],
        )
        self.assertTrue(
            all(call.args[1] == 0 for call in api.WaitForSingleObject.call_args_list)
        )

    def test_setup_failure_and_disabled_collection_preserve_body(self):
        for enabled, api in ((True, SimpleNamespace()), (False, _api())):
            with self.subTest(enabled=enabled):
                with observation.observe_owned_jobs(
                    enabled=enabled, api=api, job_class=_Job
                ) as observed:
                    if enabled:
                        self.assertEqual(
                            observed.failure_report()["state"], "setup_unavailable"
                        )
                    else:
                        self.assertIsNone(observed)
                    job = _Job()
                    self.assertTrue(job.assign(111))

    def test_unexpected_capture_failure_never_changes_original_method_result(self):
        with (
            patch.object(
                observation.JobObservations,
                "capture",
                side_effect=RuntimeError("observer"),
            ),
            observation.observe_owned_jobs(
                enabled=True, api=_api(), job_class=_Job
            ) as observed,
        ):
            job = _Job()
            self.assertTrue(job.assign(111))
            self.assertFalse(job.terminate())
            job.close()
            self.assertTrue(observed.capped)
            self.assertTrue(job._closed)
