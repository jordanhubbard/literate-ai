"""Bound framing before parsing and never confuse matching data with authority."""

import json
import unittest
from dataclasses import replace

from literate_ai.adapters.worker_telemetry_wire import (
    TelemetryWireError,
    decode_telemetry_request,
    decode_telemetry_response,
    encode_telemetry_request,
    encode_telemetry_response,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry import (
    MAX_TELEMETRY_RESPONSE_BYTES,
    MAX_TELEMETRY_SAMPLE_BYTES,
    TelemetryMeasurementScope,
    TelemetryMetricStatus,
)
from literate_ai.contracts.worker_telemetry_observations import (
    TelemetryActionState,
    TelemetryResponseStatus,
    WorkerTelemetryObservation,
)
from tests.support.fixtures_worker_telemetry import (
    telemetry_request,
    telemetry_response,
)


class WorkerTelemetryWireTests(unittest.TestCase):
    def setUp(self):
        self.request = telemetry_request()
        self.response = telemetry_response(self.request)
        self.wire = encode_telemetry_response(self.response, self.request)

    def decode(self, raw):
        return decode_telemetry_response(raw, self.request)

    def test_roundtrip_request_response_and_maximum_complete_action_batch(self):
        self.assertEqual(
            decode_telemetry_request(encode_telemetry_request(self.request)),
            self.request,
        )
        self.assertEqual(self.decode(self.wire), self.response)
        request = telemetry_request(64)
        response = telemetry_response(request)
        encoded = encode_telemetry_response(response, request)
        self.assertEqual(decode_telemetry_response(encoded, request), response)
        self.assertEqual(encoded.count(b"\n"), 65)
        self.assertLessEqual(len(encoded), MAX_TELEMETRY_RESPONSE_BYTES)
        self.assertTrue(
            all(
                len(record) + 1 <= MAX_TELEMETRY_SAMPLE_BYTES
                for record in encoded.splitlines()
            )
        )

    def test_bytes_and_aggregate_bounds_precede_json_parsing(self):
        for raw in (bytearray(self.wire), "not-bytes", None):
            with (
                self.subTest(type=type(raw).__name__),
                self.assertRaises(TelemetryWireError),
            ):
                self.decode(raw)
        with self.assertRaisesRegex(TelemetryWireError, "response_limit"):
            self.decode(b"!" * (MAX_TELEMETRY_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(TelemetryWireError, "record_limit"):
            decode_telemetry_request(b"!" * (MAX_TELEMETRY_SAMPLE_BYTES + 1))
        with self.assertRaisesRegex(TelemetryWireError, "record_limit"):
            self.decode(b"!" * MAX_TELEMETRY_SAMPLE_BYTES + b"\n")

    def test_framing_is_bounded_before_line_list_allocation(self):
        for raw in (b"", self.wire[:-1], b"\n" * 66, self.wire + b"\n"):
            with self.subTest(size=len(raw)), self.assertRaises(TelemetryWireError):
                self.decode(raw)
        with self.assertRaises(TelemetryWireError):
            decode_telemetry_request(encode_telemetry_request(self.request) + b"\n")

    def test_duplicate_keys_nonfinite_utf8_and_nested_payloads_refuse(self):
        self.assertIn(b'"sequence":0', self.wire)
        values = [
            self.wire.replace(b'"sequence":0', b'"sequence":0,"sequence":0'),
            self.wire.replace(b'"sequence":0', b'"sequence":NaN'),
            b"\xff\n",
            b"[" * 2000 + b"0" + b"]" * 2000 + b"\n",
        ]
        for raw in values:
            with self.subTest(size=len(raw)), self.assertRaises(TelemetryWireError):
                self.decode(raw)

    def test_request_worker_scope_and_expiry_cannot_be_substituted(self):
        header, sample = self.wire.splitlines()
        for field in (
            "request_identity",
            "worker_identity",
            "observation_scope_identity",
            "expires_at_ms",
        ):
            data = json.loads(header)
            data[field] = (
                40000 if field == "expires_at_ms" else canonical_identity("wrong").uri
            )
            with self.subTest(field=field), self.assertRaises(TelemetryWireError):
                self.decode(json.dumps(data).encode() + b"\n" + sample + b"\n")
        with self.assertRaises(ValueError):
            encode_telemetry_response(
                self.response, replace(self.request, nonce="b" * 64)
            )

    def test_missing_duplicate_or_unrequested_action_samples_refuse(self):
        request = telemetry_request(2)
        response = telemetry_response(request)
        for samples in (
            response.samples[:1],
            (response.samples[0],) * 2,
            response.samples[::-1],
        ):
            with self.subTest(count=len(samples)), self.assertRaises(ValueError):
                encode_telemetry_response(replace(response, samples=samples), request)
        h, s = self.wire.splitlines()
        header = json.loads(h)
        header["sample_count"] = 2
        with self.assertRaises(TelemetryWireError):
            self.decode(json.dumps(header).encode() + b"\n" + s + b"\n")

    def test_explicit_unsupported_denied_and_unavailable_are_not_zero_samples(self):
        for status in TelemetryResponseStatus:
            if status is TelemetryResponseStatus.OBSERVED:
                continue
            response = replace(self.response, status=status, samples=())
            self.assertEqual(
                self.decode(encode_telemetry_response(response, self.request)), response
            )
            with self.assertRaises(ValueError):
                replace(response, samples=self.response.samples)
        with self.assertRaises(ValueError):
            replace(self.response, samples=())

    def test_aggregate_scope_cannot_enumerate_an_action_or_relabel_job_counters(self):
        request = telemetry_request(aggregate=True)
        response = telemetry_response(request)
        self.assertEqual(
            decode_telemetry_response(
                encode_telemetry_response(response, request), request
            ),
            response,
        )
        with self.assertRaises(ValueError):
            encode_telemetry_response(self.response, request)
        sample = response.samples[0]
        with self.assertRaises(ValueError):
            replace(sample, process_start_identity=canonical_identity("foreign"))
        with self.assertRaises(ValueError):
            replace(
                sample,
                metrics=tuple(
                    replace(m, scope=TelemetryMeasurementScope.PROCESS_SUBTREE)
                    for m in sample.metrics
                ),
            )

    def test_complete_scoped_metric_inventory_and_action_owner_references_required(
        self,
    ):
        sample = self.response.samples[0]
        for change in (
            {"reservation_identity": None},
            {"process_start_identity": None},
            {"metrics": sample.metrics[:-1]},
            {"metrics": (sample.metrics[0],) * len(sample.metrics)},
        ):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                replace(sample, **change)
        measured = replace(
            sample.metrics[0], status=TelemetryMetricStatus.MEASURED, value=25
        )
        self.assertEqual(measured.scope, sample.metrics[0].scope)
        # There is no implicit promotion from host scope into process scope.
        self.assertIs(
            replace(measured, scope=TelemetryMeasurementScope.WORKER_HOST).scope,
            TelemetryMeasurementScope.WORKER_HOST,
        )

    def test_terminal_result_reference_is_required_but_does_not_authenticate_it(self):
        sample = self.response.samples[0]
        with self.assertRaises(ValueError):
            replace(sample, state=TelemetryActionState.FINISHED)
        terminal = replace(
            sample,
            state=TelemetryActionState.FINISHED,
            terminal_result_identity=canonical_identity("untrusted-result-reference"),
        )
        self.assertEqual(
            WorkerTelemetryObservation.from_dict(terminal.to_dict()), terminal
        )
        with self.assertRaises(ValueError):
            replace(terminal, state=TelemetryActionState.RUNNING)

    def test_observation_epoch_sequence_and_time_are_closed_data(self):
        for field in ("observer_epoch", "sequence"):
            value = canonical_identity("next-epoch") if field == "observer_epoch" else 1
            response = replace(self.response, **{field: value})
            self.assertEqual(
                self.decode(encode_telemetry_response(response, self.request)), response
            )
        for change in (
            {"sequence": True},
            {"sequence": -1},
            {"observed_at_ms": 31000},
            {"observed_at_ms": 1500},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.response, **change)
        with self.assertRaises(ValueError):
            encode_telemetry_response(
                replace(
                    self.response,
                    samples=(replace(self.response.samples[0], observed_at_ms=0),),
                ),
                self.request,
            )

    def test_secret_shaped_extra_fields_never_enter_public_decoder_error_text(self):
        header, sample = self.wire.splitlines()
        value = json.loads(sample)
        value["private-password-marker"] = "private-password-value"
        with self.assertRaises(TelemetryWireError) as caught:
            self.decode(header + b"\n" + json.dumps(value).encode() + b"\n")
        self.assertNotIn("private-password", str(caught.exception))
