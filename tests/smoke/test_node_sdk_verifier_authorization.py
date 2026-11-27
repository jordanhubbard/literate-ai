"""Original intent/captures with injected runtime membership; no grants/native proof."""

import dataclasses
import gc
import os
import shutil
import sys
import tempfile
import unittest
import weakref
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_authority as membership
from literate_ai.adapters import node_sdk_verifier_authorization as owner
from literate_ai.contracts import canonical_identity
from literate_ai.security.policy import OriginAttestation, SecurityProfile
from tests.smoke import test_node_sdk_verifier_runtime as runtime_fixture
from tests.smoke.test_node_sdk_cross_language import with_provider


class WeakNamespace(SimpleNamespace):
    pass


class VerifierIntentFactoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        _, self.snapshot, self.execution = with_provider(Path(temporary.name))

    def intent(self, **changes):
        arguments = dict(
            snapshot=self.snapshot,
            execution=self.execution,
            actor="isolated verifier qualification",
            reason="original captured verifier inputs",
            authorization_lifetime=timedelta(minutes=5),
            authorization_deadline=datetime.now(UTC) + timedelta(minutes=10),
            acknowledge_identity_only_inputs=True,
        )
        arguments.update(changes)
        handle = owner.acknowledge_node_sdk_verifier_execution(**arguments)
        self.addCleanup(membership._retire_acknowledgement, handle)
        return handle

    def test_fixed_intent_binds_authority_policy_and_deadline_without_a_grant(self):
        deadline = datetime.now(UTC) + timedelta(minutes=10)
        handle = self.intent(authorization_deadline=deadline)
        original = owner._original_owner(handle)
        facts = original[4]
        self.assertIs(original[1](), handle)
        self.assertIs(original[2], self.snapshot)
        self.assertIs(original[3], self.execution)
        self.assertEqual(facts[1], self.snapshot.authority.identity.uri)
        self.assertEqual(facts[4], self.execution.identity.uri)
        self.assertEqual(facts[5], owner._POLICY_ID)
        self.assertEqual(facts[10], 300_000_000)
        self.assertEqual(facts[11], deadline.isoformat())
        self.assertIs(membership._values(membership._state(handle))[3], None)
        self.assertFalse(hasattr(handle, "authorize"))

    def test_invalid_or_implicit_intent_refuses_without_registration(self):
        class Text(str):
            pass

        for changes in (
            {"acknowledge_identity_only_inputs": False},
            {"acknowledge_identity_only_inputs": 1},
            {"authorization_lifetime": timedelta(0)},
            {"authorization_lifetime": timedelta(hours=1, microseconds=1)},
            {"authorization_deadline": datetime.now()},
            {"authorization_deadline": datetime.now(UTC) - timedelta(seconds=1)},
            {"actor": Text("actor")},
            {"reason": " "},
            {"reason": "é" * 4096},
        ):
            with self.subTest(changes=tuple(changes)):
                before = len(membership._ACKNOWLEDGEMENTS)
                with self.assertRaises(ValueError):
                    self.intent(**changes)
                self.assertEqual(len(membership._ACKNOWLEDGEMENTS), before)

    def test_mismatched_execution_and_changed_snapshot_refuse_factory(self):
        with tempfile.TemporaryDirectory() as raw:
            _, _, other = with_provider(Path(raw), second_provider=True)
            with self.assertRaises(ValueError):
                self.intent(execution=other)
        # Replacement of an original snapshot field refuses even if an equal
        # value could produce the same descriptive identity.
        handle = self.intent()
        guard = owner._original_owner(handle)[5]
        original = self.snapshot._target_name
        object.__setattr__(self.snapshot, "_target_name", "changed-target")
        try:
            with self.assertRaises(ValueError):
                guard[1]()
        finally:
            object.__setattr__(self.snapshot, "_target_name", original)
            guard[2]()
        with self.assertRaisesRegex(ValueError, "released"):
            guard[0]()

    def test_fixed_issuer_has_no_strong_acknowledgement_cycle(self):
        handle = self.intent()
        reference, key = weakref.ref(handle), id(handle)
        # Remove unittest cleanup's intentional strong reference for this check.
        self._cleanups.pop()
        del handle
        gc.collect()
        self.assertIsNone(reference())
        self.assertNotIn(key, membership._ACKNOWLEDGEMENTS)

    def test_retirement_releases_original_source_with_actual_guard_traceback_retained(
        self,
    ):
        handle = self.intent()
        guard = owner._original_owner(handle)[5]
        planner = weakref.ref(self.snapshot._planner)
        original = self.snapshot._target_name
        object.__setattr__(self.snapshot, "_target_name", "changed-target")
        failure = None
        try:
            guard[0]()
        except ValueError as error:
            failure = error
        finally:
            object.__setattr__(self.snapshot, "_target_name", original)
        self.assertIsNotNone(failure)
        self.assertIsNotNone(failure.__traceback__)
        membership._retire_acknowledgement(handle)
        self.snapshot = self.execution = None
        gc.collect()
        self.assertIsNone(planner())
        for check in guard[:2]:
            with self.assertRaisesRegex(ValueError, "released"):
                check()
        self.assertIsNotNone(failure.__traceback__)

    def test_field_metadata_traps_refuse_without_callbacks(self):
        calls = []

        class Trap:
            def __eq__(self, other):
                calls.append("equal")
                raise AssertionError("field callback")

            def __ne__(self, other):
                calls.append("unequal")
                raise AssertionError("field callback")

        field = OriginAttestation.__dataclass_fields__["source_digest"]
        original = field.name
        field.name = Trap()
        try:
            with self.assertRaisesRegex(ValueError, "field metadata"):
                owner._require_fixed()
        finally:
            field.name = original
        self.assertEqual(calls, [])

    def test_non_string_field_keys_refuse_before_dictionary_lookup(self):
        calls = []

        class Key(str):
            __hash__ = str.__hash__

            def __eq__(self, other):
                calls.append(True)
                raise AssertionError("key callback")

        fields = OriginAttestation.__dataclass_fields__
        key = Key("source_digest")
        original = fields.pop("source_digest")
        fields[key] = original
        try:
            with self.assertRaisesRegex(ValueError, "field metadata"):
                owner._require_fixed()
        finally:
            fields.pop(key)
            fields["source_digest"] = original
        self.assertEqual(calls, [])


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected provider capture fixture",
)
class EnrolledVerifierClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_fixture.EnrolledCaptureFailureTests.setUpClass()

    def setUp(self):
        self.c = runtime_fixture.EnrolledCaptureFailureTests()
        with mock.patch.object(runtime_fixture, "SimpleNamespace", WeakNamespace):
            self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        f, c = self.c.fixture, self.c
        self.ack = owner.acknowledge_node_sdk_verifier_execution(
            snapshot=f.snapshot,
            execution=f.execution,
            actor="isolated classification fixture",
            reason="original captured input qualification",
            authorization_lifetime=timedelta(minutes=5),
            authorization_deadline=datetime.now(UTC) + timedelta(minutes=10),
            acknowledge_identity_only_inputs=True,
        )
        self.addCleanup(membership._retire_acknowledgement, self.ack)
        original = owner._original_owner(self.ack)
        # These two joins are deliberately injected, like the operation fixture.
        # They do not establish actual host-mode/native invocation qualification.
        c.bound.configuration.snapshot = f.snapshot
        c.bound.configuration.expected_execution = f.execution
        c.state._execution = f.execution
        membership._bind_acknowledgement(
            self.ack,
            c.bound.configuration,
            c.bound,
            facts=original[4],
            originals=(f.snapshot, f.execution),
        )

    def classify(self, handle, ticket):
        return owner._classify_enrolled_node_verifier_inputs(
            self.ack, self.c.operation, handle, ticket
        )

    def assert_failed_cleanup(self, baseline):
        self.c.state.retire()
        self.assertFalse(captures._LIVE)
        self.assertFalse(captures._RESERVED)
        self.assertFalse(captures._PENDING_CLEANUP)
        self.assertEqual(captures._RESOURCE_POOL.statistics(), baseline)

    def test_original_capture_produces_local_custody_classification_without_grant(self):
        c = self.c
        with c.capture() as (handle, ticket):
            result, observation, attestation = self.classify(handle, ticket)
            request = handle.description.request
            self.assertIs(result.profile, SecurityProfile.CONSTRAINED)
            self.assertEqual(result.permitted_privileges, ("execute-library-verifier",))
            self.assertEqual(result.source_digests, (request.source_bundle_digest,))
            self.assertFalse(observation["vendor_signature_verified"])
            self.assertEqual(
                attestation.signature_identity, canonical_identity(observation).uri
            )
            self.assertEqual(attestation.source_digest, request.source_bundle_digest)
            self.assertTrue(attestation.accepted)
            self.assertEqual(
                c.state._classifications[ticket],
                (
                    "CLASSIFIED",
                    attestation.trust_root,
                    attestation.signature_identity,
                    result.digest,
                ),
            )
            self.assertTrue(
                all(type(value) is str for value in c.state._classifications[ticket])
            )

    def test_unknown_and_executable_data_refuse_closed_policy(self):
        for path, mode in (
            ("payload.wasm", 0o644),
            ("LICENSE", 0o755),
            ("config.json", 0o700),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                owner._require_supported_coverage([{"path": path, "mode": mode}])
        owner._require_supported_coverage(
            [
                {"path": "LICENSE", "mode": 0o644},
                {"path": "NOTICE", "mode": 0o644},
                {"path": "types/api.d.mts", "mode": 0o755},
            ]
        )

    def _mutate_during_owner(
        self, install, expected, *, after_scan=True, in_request=False
    ):
        c = self.c
        baseline = captures._RESOURCE_POOL.statistics()
        ports, installed = c.fixture.ports, []
        original = ports.require_library_provider_custody
        trap = mock.Mock(side_effect=AssertionError("substituted dependency ran"))
        with (
            self.assertRaisesRegex(ValueError, "poisoned|owner ended or changed"),
            c.capture() as (handle, ticket),
        ):
            with ExitStack() as changes:

                def custody(*args, **kwargs):
                    result = original(*args, **kwargs)
                    scanned = c.state._scans.get(ticket, (None,))[0] == "SCANNED"
                    request_on_stack = False
                    frame = sys._getframe(1)
                    try:
                        while frame is not None:
                            if (
                                frame.f_code
                                is captures._ProviderInspectionOwner.request.__code__
                            ):
                                request_on_stack = True
                                break
                            frame = frame.f_back
                    finally:
                        frame = None
                    if (
                        not installed
                        and (not after_scan or scanned)
                        and (not in_request or request_on_stack)
                    ):
                        installed.append(True)
                        changes.enter_context(install(trap))
                    return result

                with mock.patch.object(
                    ports, "require_library_provider_custody", side_effect=custody
                ):
                    failure = None
                    try:
                        self.classify(handle, ticket)
                    except ValueError as error:
                        failure = error
                    self.assertIsNotNone(failure)
                    self.assertRegex(str(failure), expected)
                    trace = failure.__traceback__
                    checked = False
                    while trace is not None:
                        if (
                            trace.tb_frame.f_code.co_name
                            == "_classify_enrolled_node_verifier_inputs"
                        ):
                            checked = True
                            for name in (
                                "snapshot",
                                "execution",
                                "guard",
                                "owner",
                                "bound",
                                "configuration",
                                "state",
                                "acknowledgement",
                                "rows",
                            ):
                                self.assertIsNone(trace.tb_frame.f_locals[name])
                        trace = trace.tb_next
                    self.assertTrue(checked)
                self.assertTrue(installed)
                self.assertEqual(trap.mock_calls, [])
        with self.assertRaises(ValueError):
            membership._state(self.ack)
        self.assert_failed_cleanup(baseline)

    def test_owner_substituted_security_serializer_refuses_before_invocation(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(owner.security, "json", trap),
            "dependency changed",
        )

    def test_owner_substituted_dataclass_serializer_refuses_before_invocation(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(dataclasses, "_asdict_inner", trap),
            "dependency changed",
        )

    def test_owner_substituted_request_builder_refuses_before_invocation(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(owner.requests, "_document", trap),
            "dependency changed",
        )

    def test_first_owner_request_builder_mutation_refuses_inside_original_capture(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(owner.requests, "_document", trap),
            "dependency changed",
            after_scan=False,
        )

    def test_nested_request_custody_parser_mutation_refuses_before_invocation(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(owner.requests, "_document", trap),
            "dependency changed",
            in_request=True,
        )

    def test_nested_request_custody_serializer_mutation_refuses_before_invocation(self):
        self._mutate_during_owner(
            lambda trap: mock.patch.object(owner.security, "json", trap),
            "dependency changed",
            in_request=True,
        )

    def test_owner_reentry_poison_cannot_publish_classification(self):
        c = self.c
        baseline = captures._RESOURCE_POOL.statistics()
        ports, entered = c.fixture.ports, []
        original = ports.require_library_provider_custody
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):

            def custody(*args, **kwargs):
                if not entered:
                    entered.append(True)
                    with self.assertRaises(ValueError):
                        self.classify(handle, ticket)
                return original(*args, **kwargs)

            with mock.patch.object(
                ports, "require_library_provider_custody", side_effect=custody
            ):
                with self.assertRaises(ValueError):
                    self.classify(handle, ticket)
            self.assertEqual(entered, [True])
            self.assertEqual(c.state._classifications[ticket][0], "FAILED")
        self.assert_failed_cleanup(baseline)
