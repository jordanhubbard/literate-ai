"""Real message MACs and bounded byte streams; no live-worker permission claim."""

import io
import json
import unittest
from dataclasses import replace

from literate_ai.adapters.worker_telemetry_authentication import (
    TelemetryAuthenticationError,
    TelemetryObservationCredential,
    authenticate_telemetry_request,
    authenticate_telemetry_response,
    read_telemetry_envelope,
    sign_telemetry_request,
    sign_telemetry_response,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry import MAX_TELEMETRY_RESPONSE_BYTES
from tests.support.fixtures_worker_telemetry import (
    telemetry_request,
    telemetry_response,
)


class WorkerTelemetryAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.request = telemetry_request()
        self.response = telemetry_response(self.request)
        self.controller = TelemetryObservationCredential(
            self.request.controller_identity,
            b"controller-private-fixture-key-not-a-real-secret",
        )
        self.worker = TelemetryObservationCredential(
            self.request.worker_identity,
            b"worker-private-fixture-key-not-a-real-secret",
        )
        self.signed_request = sign_telemetry_request(self.request, self.controller)
        self.signed_response = sign_telemetry_response(
            self.response, self.request, self.worker
        )

    def test_explicit_observation_credentials_authenticate_both_principals(self):
        self.assertEqual(
            authenticate_telemetry_request(
                self.signed_request, self.controller, now_ms=2000
            ),
            self.request,
        )
        self.assertEqual(
            authenticate_telemetry_response(
                self.signed_response, self.request, self.worker, now_ms=2000
            ),
            self.response,
        )
        self.assertNotIn(self.controller._secret.decode(), repr(self.controller))
        self.assertNotIn(self.controller._secret, self.signed_request)
        self.assertNotIn(self.worker._secret, self.signed_response)

    def test_no_missing_weak_mutable_or_foreign_credential_is_accepted(self):
        for raw in (b"short", bytearray(b"x" * 32), "x" * 32, b"x" * 4097):
            with self.subTest(type=type(raw).__name__), self.assertRaises(ValueError):
                TelemetryObservationCredential(self.request.controller_identity, raw)
        for credential in (
            None,
            self.worker,
            TelemetryObservationCredential(self.request.controller_identity, b"x" * 32),
        ):
            with (
                self.subTest(credential=type(credential).__name__),
                self.assertRaises(ValueError),
            ):
                authenticate_telemetry_request(
                    self.signed_request, credential, now_ms=2000
                )
        with self.assertRaises(ValueError):
            sign_telemetry_request(self.request, self.worker)
        with self.assertRaises(ValueError):
            sign_telemetry_response(self.response, self.request, self.controller)

    def test_raw_body_and_header_changes_require_a_new_mac(self):
        header, body = self.signed_request.split(b"\n", 1)
        for change in (
            {"body_bytes": True},
            {"body_bytes": len(body) + 1},
            {"key_identity": canonical_identity("wrong").uri},
            {"principal_identity": canonical_identity("foreign").uri},
            {"signature": "0" * 64},
            {"unknown-private-marker": "private-value"},
        ):
            d = json.loads(header)
            d.update(change)
            with (
                self.subTest(field=list(change)),
                self.assertRaises(TelemetryAuthenticationError),
            ):
                authenticate_telemetry_request(
                    json.dumps(d).encode() + b"\n" + body, self.controller, now_ms=2000
                )
        with self.assertRaises(TelemetryAuthenticationError):
            authenticate_telemetry_request(
                header
                + b"\n"
                + body.replace(b'"expires_at_ms":31000', b'"expires_at_ms":30000'),
                self.controller,
                now_ms=2000,
            )

    def test_request_response_domains_refuse_same_principal_reflection(
        self,
    ):
        request = replace(
            self.request, worker_identity=self.request.controller_identity
        )
        response = telemetry_response(request)
        outgoing = sign_telemetry_response(response, request, self.controller)
        with self.assertRaises(TelemetryAuthenticationError):
            authenticate_telemetry_request(outgoing, self.controller, now_ms=2000)
        with self.assertRaises(TelemetryAuthenticationError):
            authenticate_telemetry_response(
                sign_telemetry_request(request, self.controller),
                request,
                self.controller,
                now_ms=2000,
            )

    def test_authenticated_body_cannot_select_another_request_worker_or_registration(
        self,
    ):
        for change in (
            {"nonce": "b" * 64},
            {"registration_identity": canonical_identity("foreign")},
            {"observation_scope_identity": canonical_identity("other-permission")},
        ):
            request = replace(self.request, **change)
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                authenticate_telemetry_response(
                    self.signed_response, request, self.worker, now_ms=2000
                )
        with self.assertRaises(ValueError):
            authenticate_telemetry_response(
                self.signed_response,
                replace(
                    self.request, worker_identity=canonical_identity("other-worker")
                ),
                self.worker,
                now_ms=2000,
            )

    def test_expired_future_and_future_observation_values_refuse(self):
        for now in (0, 31000, 31001, True, -1):
            with self.subTest(now=now), self.assertRaises(ValueError):
                authenticate_telemetry_request(
                    self.signed_request, self.controller, now_ms=now
                )
        with self.assertRaises(ValueError):
            authenticate_telemetry_response(
                self.signed_response, self.request, self.worker, now_ms=1999
            )
        with self.assertRaises(ValueError):
            authenticate_telemetry_response(
                self.signed_response, self.request, self.worker, now_ms=31000
            )

    def test_credential_authentication_does_not_claim_replay_or_scope_authorization(
        self,
    ):
        # The nonce owner belongs to the receiver, not this stateless MAC codec.
        first = authenticate_telemetry_request(
            self.signed_request, self.controller, now_ms=2000
        )
        second = authenticate_telemetry_request(
            self.signed_request, self.controller, now_ms=2000
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first.observation_scope_identity, self.request.observation_scope_identity
        )
        foreign = replace(
            self.request,
            observation_scope_identity=canonical_identity("not-a-permission"),
        )
        self.assertEqual(
            authenticate_telemetry_request(
                sign_telemetry_request(foreign, self.controller),
                self.controller,
                now_ms=2000,
            ),
            foreign,
        )
        # A real receiver must reject that scope using its separate current owner;
        # cryptographic principal authentication intentionally cannot grant it.

    def test_duplicate_metadata_and_size_failures_do_not_echo_private_values(self):
        header, body = self.signed_request.split(b"\n", 1)
        invalid = (
            header[:-1]
            + b',"private-password-marker":"private-password-value"}\n'
            + body
        )
        with self.assertRaises(TelemetryAuthenticationError) as caught:
            authenticate_telemetry_request(invalid, self.controller, now_ms=2000)
        self.assertNotIn("private-password", str(caught.exception))
        duplicate = (
            header.replace(b'"body_bytes":', b'"body_bytes":1,"body_bytes":')
            + b"\n"
            + body
        )
        with self.assertRaises(TelemetryAuthenticationError):
            authenticate_telemetry_request(duplicate, self.controller, now_ms=2000)
        with self.assertRaisesRegex(TelemetryAuthenticationError, "size_limit"):
            authenticate_telemetry_response(
                b"!" * (MAX_TELEMETRY_RESPONSE_BYTES + 1),
                self.request,
                self.worker,
                now_ms=2000,
            )

    def test_bounded_reader_returns_exact_request_and_maximum_action_response(self):
        self.assertEqual(
            read_telemetry_envelope(io.BytesIO(self.signed_request), response=False),
            self.signed_request,
        )
        request = telemetry_request(64)
        response = telemetry_response(request)
        signed = sign_telemetry_response(response, request, self.worker)
        self.assertEqual(
            read_telemetry_envelope(io.BytesIO(signed), response=True), signed
        )
        self.assertEqual(
            authenticate_telemetry_response(signed, request, self.worker, now_ms=2000),
            response,
        )

    def test_reader_limits_precede_retention_and_no_unbounded_read_is_requested(self):
        class Instrumented(io.BytesIO):
            def __init__(self, raw):
                super().__init__(raw)
                self.requests = []

            def readline(self, size=-1):
                self.requests.append(size)
                if size < 0:
                    raise AssertionError("unbounded read")
                return super().readline(size)

        source = Instrumented(b"!" * 20000 + b"\n")
        with self.assertRaises(TelemetryAuthenticationError):
            read_telemetry_envelope(source, response=True)
        self.assertEqual(source.tell(), 1025)
        source = Instrumented(self.signed_request + b"\n" * 10000)
        with self.assertRaises(TelemetryAuthenticationError):
            read_telemetry_envelope(source, response=False)
        self.assertLessEqual(source.tell(), len(self.signed_request) + 1)
        self.assertTrue(all(0 < n <= 16385 for n in source.requests))

    def test_reader_rejects_missing_newlines_empty_and_nonbinary_streams(self):
        for stream in (
            io.BytesIO(b""),
            io.BytesIO(self.signed_request[:-1]),
            io.StringIO("hello\n"),
        ):
            with (
                self.subTest(type=type(stream).__name__),
                self.assertRaises(TelemetryAuthenticationError),
            ):
                read_telemetry_envelope(stream, response=False)
        with self.assertRaises(TelemetryAuthenticationError):
            read_telemetry_envelope(io.BytesIO(self.signed_request), response=1)
