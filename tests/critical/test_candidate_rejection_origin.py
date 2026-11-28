"""Controller-local origin bookkeeping; no generation or native qualification."""

from __future__ import annotations

import copy
import os
import unittest
from dataclasses import dataclass
from unittest import mock

from literate_ai.application import standard_project_lifecycle as lifecycle


@dataclass(frozen=True)
class _EqualData:
    value: int


class CandidateRejectionOriginTests(unittest.TestCase):
    def test_exact_original_objects_match_once(self):
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        failure, output = _EqualData(1), _EqualData(2)
        origin.record(failure, output)
        self.assertTrue(origin.matches_and_close(failure, output))
        self.assertFalse(origin.matches_and_close(failure, output))
        with self.assertRaises(lifecycle.StandardProjectLifecycleError):
            origin.record(failure, output)

    def test_copy_equal_failure_or_output_never_restores_origin(self):
        failure, output = _EqualData(1), _EqualData(2)
        for old_failure, old_output in (
            (copy.copy(failure), output),
            (failure, copy.copy(output)),
        ):
            with self.subTest(failure_is_original=old_failure is failure):
                origin = lifecycle._GeneratedCandidateRejectionOrigin()
                origin.record(failure, output)
                self.assertFalse(origin.matches_and_close(old_failure, old_output))
                self.assertFalse(origin.matches_and_close(failure, output))

    def test_empty_or_closed_scope_has_no_origin(self):
        failure, output = object(), object()
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        self.assertFalse(origin.matches_and_close(failure, output))
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        origin.record(failure, output)
        origin.close()
        self.assertFalse(origin.matches_and_close(failure, output))

    def test_old_callback_is_not_reactivated_by_the_next_attempt(self):
        first = lifecycle._GeneratedCandidateRejectionOrigin()
        callback = first.record
        first.close()
        second = lifecycle._GeneratedCandidateRejectionOrigin()
        failure, output = object(), object()
        with self.assertRaises(lifecycle.StandardProjectLifecycleError):
            callback(failure, output)
        self.assertFalse(second.matches_and_close(failure, output))

    def test_ambiguous_second_return_revokes_the_first_observation(self):
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        failure, output = object(), object()
        origin.record(failure, output)
        with self.assertRaises(lifecycle.StandardProjectLifecycleError):
            origin.record(object(), output)
        self.assertFalse(origin.matches_and_close(failure, output))

    def test_copied_scope_cannot_mint_or_consume_the_original_origin(self):
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        failure, output = object(), object()
        duplicate = copy.copy(origin)
        with self.assertRaises(lifecycle.StandardProjectLifecycleError):
            duplicate.record(failure, output)
        self.assertFalse(duplicate.matches_and_close(failure, output))
        duplicate.close()
        origin.record(failure, output)
        self.assertTrue(origin.matches_and_close(failure, output))

    def test_other_process_refuses_without_acquiring_an_inherited_lock(self):
        origin = lifecycle._GeneratedCandidateRejectionOrigin()
        failure, output = object(), object()
        parent_pid = os.getpid()
        with (
            mock.patch.object(lifecycle.os, "getpid", return_value=parent_pid + 1),
            mock.patch.object(origin, "_lock") as lock,
        ):
            lock.__enter__.side_effect = AssertionError("inherited lock was touched")
            with self.assertRaises(lifecycle.StandardProjectLifecycleError):
                origin.record(failure, output)
            self.assertFalse(origin.matches_and_close(failure, output))
            origin.close()
            lock.__enter__.assert_not_called()
        origin.close()
