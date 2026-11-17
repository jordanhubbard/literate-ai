"""ADR 0059 observational contracts reject selectors and invented measurements."""

import unittest
from dataclasses import replace

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry import (
    TelemetryMeasurementScope,
    TelemetryMetricName,
    TelemetryMetricStatus,
    TelemetryProgressReason,
    TelemetryScope,
    WorkerTelemetryMetric,
    WorkerTelemetryProgress,
    WorkerTelemetryRequest,
)


def identity(value):
    return canonical_identity(value)


class WorkerTelemetryContractTests(unittest.TestCase):
    def request(self):
        return WorkerTelemetryRequest(
            *(
                identity(name)
                for name in (
                    "controller",
                    "catalog",
                    "registration",
                    "worker",
                    "permission",
                )
            ),
            "a" * 64,
            1000,
            31000,
            TelemetryScope.ACTIONS,
            (identity("action"),),
        )

    def metric(self):
        return WorkerTelemetryMetric(
            TelemetryMetricName.NETWORK_IN_BYTES,
            TelemetryMeasurementScope.WORKER_HOST,
            TelemetryMetricStatus.UNSUPPORTED,
            None,
        )

    def test_roundtrip_binds_every_request_selection_and_permission_fact(self):
        request = self.request()
        self.assertEqual(WorkerTelemetryRequest.from_dict(request.to_dict()), request)
        for field in (
            "controller_identity",
            "catalog_identity",
            "registration_identity",
            "worker_identity",
            "observation_scope_identity",
        ):
            with self.subTest(field=field):
                self.assertNotEqual(
                    replace(request, **{field: identity("changed")}).identity,
                    request.identity,
                )
        self.assertNotEqual(replace(request, nonce="b" * 64).identity, request.identity)
        self.assertNotEqual(
            replace(request, expires_at_ms=30000).identity, request.identity
        )
        self.assertNotEqual(
            replace(request, action_identities=(identity("other-action"),)).identity,
            request.identity,
        )

    def test_no_pid_path_command_environment_or_untrusted_free_text_selector(self):
        for name in (
            "pid",
            "path",
            "command",
            "environment",
            "stdout",
            "stderr",
            "stage",
            "display_name",
            "execution_grant",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                WorkerTelemetryRequest.from_dict(
                    {**self.request().to_dict(), name: "private-sentinel"}
                )
        with self.assertRaises(ValueError):
            replace(self.request(), nonce="private-sentinel")

    def test_action_count_unique_canonical_order_and_aggregate_scope(self):
        actions = tuple(sorted((identity(n) for n in range(64)), key=lambda i: i.uri))
        self.assertEqual(
            len(replace(self.request(), action_identities=actions).action_identities),
            64,
        )
        for value in (
            actions + (identity("65"),),
            actions[::-1],
            (actions[0], actions[0]),
            (),
            list(actions),
        ):
            with (
                self.subTest(value_type=type(value).__name__),
                self.assertRaises(ValueError),
            ):
                replace(self.request(), action_identities=value)
        aggregate = replace(
            self.request(), scope=TelemetryScope.WORKER_AGGREGATE, action_identities=()
        )
        self.assertNotEqual(aggregate.identity, self.request().identity)
        with self.assertRaises(ValueError):
            replace(aggregate, action_identities=actions)
        with self.assertRaises(ValueError):
            WorkerTelemetryRequest.from_dict(
                {
                    **self.request().to_dict(),
                    "action_identities": ["not-an-identity"] * 65,
                }
            )

    def test_deadline_strict_integer_finite_30_second_window(self):
        for change in (
            {"issued_at_ms": True},
            {"expires_at_ms": False},
            {"issued_at_ms": -1},
            {"expires_at_ms": 1000},
            {"expires_at_ms": 31001},
            {"expires_at_ms": 2**63},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.request(), **change)

    def test_all_unmeasured_statuses_are_null_and_preserve_measurement_scope(self):
        for status in TelemetryMetricStatus:
            if status is TelemetryMetricStatus.MEASURED:
                continue
            metric = replace(self.metric(), status=status)
            self.assertEqual(WorkerTelemetryMetric.from_dict(metric.to_dict()), metric)
            self.assertIsNone(metric.value)
            self.assertEqual(metric.scope, TelemetryMeasurementScope.WORKER_HOST)
            with self.assertRaises(ValueError):
                replace(metric, value=0)
        # A reported zero must be an actual measured counter, not unavailable data.
        measured = replace(
            self.metric(), status=TelemetryMetricStatus.MEASURED, value=0
        )
        self.assertEqual(WorkerTelemetryMetric.from_dict(measured.to_dict()), measured)

    def test_metric_units_and_counter_gauge_meanings_cannot_be_relabelled(self):
        for name in TelemetryMetricName:
            metric = replace(self.metric(), name=name)
            self.assertEqual(WorkerTelemetryMetric.from_dict(metric.to_dict()), metric)
            for change in (
                {"unit": "seconds"},
                {"cumulative": not metric.cumulative},
                {"cumulative": int(metric.cumulative)},
                {"command": "secret"},
            ):
                with (
                    self.subTest(name=name, change=change),
                    self.assertRaises(ValueError),
                ):
                    WorkerTelemetryMetric.from_dict({**metric.to_dict(), **change})

    def test_metric_numbers_and_closed_names_scopes_statuses(self):
        for value in (None, True, -1, float("nan"), float("inf"), 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(
                    self.metric(), status=TelemetryMetricStatus.MEASURED, value=value
                )
        with self.assertRaises(ValueError):
            replace(self.metric(), name="unrestricted-log-line")
        with self.assertRaises(ValueError):
            replace(self.metric(), scope="job")
        with self.assertRaises(ValueError):
            replace(self.metric(), status="measured", value=0)
        with self.assertRaises(ValueError):
            replace(
                self.metric(),
                name=TelemetryMetricName.CPU_UTILIZATION_BASIS_POINTS,
                status=TelemetryMetricStatus.MEASURED,
                value=10001,
            )

    def test_indeterminate_progress_has_typed_reason_and_no_made_up_percentage(self):
        for reason in TelemetryProgressReason:
            progress = WorkerTelemetryProgress(reason=reason)
            self.assertEqual(
                WorkerTelemetryProgress.from_dict(progress.to_dict()), progress
            )
            self.assertIsNone(progress.completed)
            self.assertIsNone(progress.total)
        for value in (None, "elapsed-time-implies-half-done", "secret-marker"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                WorkerTelemetryProgress(reason=value)

    def test_progress_known_work_is_bounded_consistent_and_not_boolean(self):
        progress = WorkerTelemetryProgress(3, 10, None)
        self.assertEqual(
            WorkerTelemetryProgress.from_dict(progress.to_dict()), progress
        )
        for completed, total in (
            (None, 10),
            (0, None),
            (0, 0),
            (11, 10),
            (-1, 10),
            (True, 10),
            (1, False),
            (0, 2**63),
        ):
            with (
                self.subTest(completed=completed, total=total),
                self.assertRaises(ValueError),
            ):
                WorkerTelemetryProgress(completed, total, None)
        with self.assertRaises(ValueError):
            WorkerTelemetryProgress(3, 10, TelemetryProgressReason.OPAQUE_WORK)
        with self.assertRaises(ValueError):
            WorkerTelemetryProgress.from_dict({**progress.to_dict(), "percentage": 30})
