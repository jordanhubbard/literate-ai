"""Closed negative protocol controls; commands/results are modeled, not native.

The genuine executor/input guards create records under controlled process seams.
The predicates reopen records without commands; this is not historical source,
package, producer-authenticity or qualification proof.
"""

import copy
import hashlib
import inspect
import json
import os
import unittest
from contextlib import contextmanager
from unittest import mock

from literate_ai.adapters import rust_library_harness_execution as execution
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.adapters.native_root_rejection_replay import (
    verify_closed_rust_harness_value_rejection,
)
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from tests.critical import test_rust_harness_outcome as fixture


@unittest.skipUnless(os.name == "posix", "owned local POSIX protocol fixtures")
class NativeRootRejectionReplayTests(unittest.TestCase):
    setUp = fixture.RustHarnessOutcomeTests.setUp
    observe = fixture.RustHarnessOutcomeTests.observe
    metadata = fixture.RustHarnessOutcomeTests.metadata
    library_current = fixture.RustHarnessOutcomeTests.library_current
    native_protocol = fixture.RustHarnessOutcomeTests.native_protocol
    binding = fixture.RustHarnessOutcomeTests.binding

    def record(self, payload):
        identity = ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(payload).hexdigest()
        )
        self.records[identity] = payload
        return identity

    def collect(self, mode="values"):
        self.records = {}
        self.mode = mode
        original = execution._observe_rust_library_harness_outcome

        @contextmanager
        def capture(oracle, **kwargs):
            kwargs["record_bytes"] = self.record
            with original(oracle, **kwargs) as outcome:
                self.document = copy.deepcopy(outcome.observation)
                self.record(canonical_json_bytes(self.document))
                yield outcome

        with mock.patch.object(
            execution, "_observe_rust_library_harness_outcome", capture
        ):
            fixture.RustHarnessOutcomeTests.operate(self, lambda *_: None)
        self.identity = self.record(canonical_json_bytes(self.document))

    def reader(self):
        return QualificationEvidenceReader(
            tuple(sorted(self.records.items(), key=lambda row: row[0].uri)),
            max_bytes=64 * 1024**2,
            max_records=128,
        )

    def verify(self, *, positive=False, document=None, reader=None):
        identity = (
            self.identity
            if document is None
            else self.record(canonical_json_bytes(document))
        )
        predicate = (
            execution.verify_rust_harness_execution
            if positive
            else verify_closed_rust_harness_value_rejection
        )
        return predicate(
            self.reader() if reader is None else reader,
            identity,
            oracle=self.fixture.oracle,
            library_alias=self.fixture.surface.package,
            surface=self.fixture.surface,
        )

    def test_values_differ_passes_negative_but_strict_positive_still_refuses(
        self,
    ):
        self.collect()
        with mock.patch.object(
            execution,
            "run_bounded_process",
            side_effect=AssertionError("replay cannot execute"),
        ) as process:
            self.assertIsNone(self.verify())
            with self.assertRaises(ComponentAcceptanceError) as caught:
                self.verify(positive=True)
        self.assertEqual(
            caught.exception.code, "component_acceptance.rust_harness_result_mismatch"
        )
        process.assert_not_called()

    def test_fixed_positive_still_accepts_matching_result_and_negative_refuses(self):
        self.collect("match")
        self.assertIsNone(self.verify(positive=True))
        with self.assertRaises(ComponentAcceptanceError) as caught:
            self.verify()
        self.assertEqual(
            caught.exception.code,
            "component_acceptance.rust_harness_archive_result_matches",
        )

    def test_neither_public_entry_exposes_a_result_relaxation_argument(self):
        expected = ("reader", "identity", "oracle", "library_alias", "surface")
        for predicate in (
            execution.verify_rust_harness_execution,
            verify_closed_rust_harness_value_rejection,
        ):
            self.assertEqual(tuple(inspect.signature(predicate).parameters), expected)
            with self.assertRaises(TypeError):
                predicate(
                    None,
                    None,
                    oracle=None,
                    library_alias=None,
                    surface=None,
                    allow_rejection=True,
                )

    def test_wrong_inventory_capability_duplicate_and_nonfinite_protocol_refuse(
        self,
    ):
        self.collect()
        row = self.document["commands"][-1]
        baseline = json.loads(
            self.records[ContentIdentity.parse_uri(row["stdout_identity"])]
        )
        payloads = []
        for field, replacement in (
            ("case_id", "foreign-case"),
            ("capability", "foreign-capability"),
        ):
            result = copy.deepcopy(baseline)
            result["cases"][0][field] = replacement
            payloads.append(json.dumps(result).encode())
        result = copy.deepcopy(baseline)
        result["cases"].append(copy.deepcopy(result["cases"][0]))
        payloads.extend(
            (
                json.dumps(result).encode(),
                b'{"schema":"x","schema":"y","cases":[]}',
                b'{"schema":"literate-ai/library-acceptance-results@1","cases":[NaN]}',
                b"not json",
            )
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                changed = copy.deepcopy(self.document)
                changed["commands"][-1]["stdout_identity"] = self.record(payload).uri
                for positive in (False, True):
                    with self.assertRaises((ComponentAcceptanceError, ValueError)):
                        self.verify(document=changed, positive=positive)

    def test_rehashed_failed_process_and_wrong_command_order_refuse(self):
        self.collect()
        for index in range(4):
            changed = copy.deepcopy(self.document)
            changed["commands"][index]["exit_code"] = 1
            with self.subTest(index=index), self.assertRaises(ComponentAcceptanceError):
                self.verify(document=changed)
        changed = copy.deepcopy(self.document)
        changed["commands"][0], changed["commands"][1] = (
            changed["commands"][1],
            changed["commands"][0],
        )
        with self.assertRaises(ComponentAcceptanceError):
            self.verify(document=changed)

    def test_missing_executable_or_any_raw_stream_refuses(self):
        self.collect()
        identities = [self.document["native_verifier_identity"]]
        identities.extend(
            row[name]
            for row in self.document["commands"]
            for name in ("stdout_identity", "stderr_identity")
        )
        for uri in set(identities):
            identity = ContentIdentity.parse_uri(uri)
            payload = self.records.pop(identity)
            with (
                self.subTest(identity=identity),
                self.assertRaises(QualificationCaptureError),
            ):
                self.verify()
            self.records[identity] = payload

    def test_rehashed_empty_executable_tool_and_input_identity_substitution_refuse(
        self,
    ):
        self.collect()
        for field in (
            "native_verifier_identity",
            "cargo_toolchain_identity",
            "input_owners_identity",
            "verifier_inputs_identity",
        ):
            changed = copy.deepcopy(self.document)
            changed[field] = self.record(b"").uri
            with self.subTest(field=field), self.assertRaises(ComponentAcceptanceError):
                self.verify(document=changed)
        changed = copy.deepcopy(self.document)
        changed["cargo_observation"]["version"] = "foreign observer"
        with self.assertRaises(ComponentAcceptanceError):
            self.verify(document=changed)

    def test_changed_current_trusted_verifier_input_refuses_negative_history(self):
        self.collect()
        (self.fixture.authority / "Cargo.lock").write_bytes(
            b"# changed current verifier input\n"
        )
        with self.assertRaises((ComponentAcceptanceError, ValueError)):
            self.verify()
