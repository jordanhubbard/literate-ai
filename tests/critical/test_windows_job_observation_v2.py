"""Real thread/feed handoff with a modeled Job; no native Windows acceptance."""

import threading
import unittest
from unittest import mock

from literate_ai.adapters import _processes
from literate_ai.adapters.windows_job_numeric_feed import (
    NumericFeedUnavailable,
    NumericJobFeed,
)
from tests.critical import test_windows_job_fallback as fallback


class WindowsJobObservationHandoffV2Tests(unittest.TestCase):
    terminate = fallback.WindowsJobFallbackTests.terminate

    def owner(self):
        job = mock.Mock(_closed=False)
        job.terminate.return_value = True
        owner = _processes.ProcessTreeOwnership({}, job)
        feed = NumericJobFeed(epoch="a" * 64)
        control = tuple(threading.Event() for _ in range(3))
        self.assertTrue(owner.begin_windows_job_observation(feed, control))
        self.addCleanup(owner.finish_windows_job_observation)
        self.addCleanup(owner.release)
        return owner, job, feed, control

    def foreign(self, operation):
        results = []
        errors = []

        def call():
            try:
                results.append(operation())
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=call, daemon=True)
        thread.start()
        thread.join(5)
        self.assertFalse(thread.is_alive(), "foreign cleanup did not return")
        self.assertEqual(errors, [])
        return results[0]

    def test_foreign_termination_defers_without_fallback_or_false_kill_proof(self):
        owner, job, feed, control = self.owner()
        process, popen = self.foreign(lambda: self.terminate(owner, running=True))
        popen.assert_not_called()
        process.kill.assert_not_called()
        job.terminate.assert_not_called()
        job.close.assert_not_called()
        self.assertTrue(control[0].is_set())
        self.assertTrue(control[1].is_set())
        self.assertFalse(self.foreign(owner.terminate))
        self.assertEqual(owner.take_windows_job_control_request(), "terminate")
        process, popen = self.terminate(owner, running=True)
        popen.assert_not_called()
        process.kill.assert_not_called()
        job.terminate.assert_called_once_with()
        job.close.assert_called_once_with()
        self.assertTrue(owner.terminate())
        with self.assertRaises(NumericFeedUnavailable):
            feed.snapshot()

    def test_foreign_release_keeps_job_until_original_runner_consumes_request(self):
        owner, job, _feed, control = self.owner()
        self.foreign(owner.release)
        job.close.assert_not_called()
        self.assertIs(owner.job, job)
        self.assertTrue(control[0].is_set())
        self.assertEqual(owner.take_windows_job_control_request(), "release")
        owner.release()
        job.close.assert_called_once_with()
        job.terminate.assert_not_called()
        self.assertFalse(owner.terminate())

    def test_sampling_failure_disables_only_observation(self):
        with mock.patch.object(
            _processes,
            "read_original_job_accounting",
            side_effect=OSError("modeled unavailable native counter"),
        ) as read:
            owner, job, feed, _control = self.owner()
        owner.sample_windows_job_observation()
        read.assert_called_once_with(job._kernel32, job._handle)
        self.assertIs(owner.job, job)
        job.terminate.assert_not_called()
        job.close.assert_not_called()
        self.assertIsNone(owner.take_windows_job_control_request())
        with self.assertRaises(NumericFeedUnavailable):
            feed.snapshot()
