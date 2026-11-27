"""Bounded source-only diagnostic controls; no SDK qualification."""

import gc
import json
import os
import tempfile
import threading
import unittest
import weakref
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from literate_ai.contracts import canonical_identity
from literate_ai.security import (
    AuthorizationError,
    BuildAuthorization,
    BuildRequest,
    SecurityProfile,
)
from tests.support import sdk_runtime_diagnostic as diagnostic

ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64


def request():
    return BuildRequest(
        DIGEST, DIGEST, "fixture-build@1", DIGEST, "fixture", ("compiler",), ("stdout",)
    )


def grant(value, identifier="DO-NOT-RECORD-AUTHORIZATION"):
    now = datetime(2026, 11, 19, tzinfo=UTC)
    return BuildAuthorization(
        identifier,
        DIGEST,
        canonical_identity(value.to_dict()).uri,
        DIGEST,
        "DO-NOT-RECORD-ACTOR",
        "DO-NOT-RECORD-REASON",
        SecurityProfile.CONSTRAINED,
        value.requested_privileges,
        now,
        now + timedelta(minutes=1),
    )


class SDKRuntimeDiagnosticTests(unittest.TestCase):
    def test_output_is_bounded_private_and_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            base = root / "_build" / "sealed-js-imports"
            base.mkdir(parents=True)
            target = base / "diagnostic.json"
            report = {"qualified": False, "capture_incomplete": True}
            diagnostic.persist_runtime_diagnostic(root, target, report)
            self.assertEqual(json.loads(target.read_bytes()), report)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                diagnostic.persist_runtime_diagnostic(root, target, report)
            self.assertEqual(json.loads(target.read_bytes()), report)

    def test_output_refuses_escape_symlink_overflow_and_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            base = root / "_build" / "sealed-js-imports"
            base.mkdir(parents=True)
            target = base / "diagnostic.json"
            target.symlink_to(root / "absent.json")
            for output in (target, root / "escape.json", base / "../escape.json"):
                with self.assertRaises(ValueError):
                    diagnostic.diagnostic_output_path(root, output)
            target.unlink()
            for report in (
                {"qualified": True},
                {"qualified": False, "payload": "x" * 32768},
            ):
                with self.assertRaises(ValueError):
                    diagnostic.persist_runtime_diagnostic(root, target, report)
            self.assertFalse(target.exists())
            base.rmdir()
            base.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                diagnostic.diagnostic_output_path(root, target)

    def test_output_exclusive_open_refuses_racing_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            base = root / "_build" / "sealed-js-imports"
            base.mkdir(parents=True)
            target = base / "diagnostic.json"
            original = os.open

            def racing_open(path, flags, *args, **kwargs):
                if path == target.name:
                    target.write_bytes(b"retained evidence")
                return original(path, flags, *args, **kwargs)

            with mock.patch.object(diagnostic.os, "open", side_effect=racing_open):
                with self.assertRaises(FileExistsError):
                    diagnostic.persist_runtime_diagnostic(
                        root, target, {"qualified": False}
                    )
            self.assertEqual(target.read_bytes(), b"retained evidence")

    def test_only_target_thread_metadata_without_paths_locals_or_arguments(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        secret = "DO-NOT-RECORD-LOCAL-DATA"
        stop = threading.Event()
        entered = threading.Event()

        def other_thread_marker():
            private = secret
            entered.set()
            stop.wait(2)
            return private

        thread = threading.Thread(target=other_thread_marker)
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            with observer.observe():
                observer._sample()
                observer.record_lifecycle_cleanup(True)
        finally:
            stop.set()
            thread.join(timeout=2)
        report = observer.snapshot()
        encoded = json.dumps(report)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(str(ROOT), encoded)
        self.assertTrue(report["frames"])
        self.assertNotIn(
            "other_thread_marker", {row["function"] for row in report["frames"]}
        )
        self.assertTrue(report["cleanup_complete"])
        self.assertFalse(report["capture_active"])
        self.assertFalse(report["qualified"])

    def test_original_grant_calls_times_role_and_expiry_are_preserved(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        build_request = request()
        build_grant = grant(build_request)
        provider_request = replace(
            build_request,
            builder_id="local-node-provider-verifier@1",
            requested_privileges=("execute-library-verifier",),
        )
        provider_grant = grant(provider_request, "DO-NOT-RECORD-VERIFIER-ID")
        original = BuildAuthorization.require_valid
        clock_calls = []

        def clock(value):
            clock_calls.append(True)
            return value

        with mock.patch.object(
            BuildAuthorization, "require_valid", wraps=original
        ) as delegate:
            with observer.observe():
                build_grant.require_valid(
                    build_request, now=clock(build_grant.issued_at)
                )
                provider_grant.require_valid(
                    provider_request, now=clock(provider_grant.issued_at)
                )
                with self.assertRaises(AuthorizationError) as failure:
                    build_grant.require_valid(
                        build_request, now=clock(build_grant.expires_at)
                    )
            self.assertEqual(delegate.call_count, 3)
        self.assertEqual(len(clock_calls), 3)
        self.assertEqual(failure.exception.code, "security.authorization_expired")
        rows = observer.snapshot()["grants"]
        self.assertEqual(len(rows), 2)
        failed = next(row for row in rows if "failure" in row)
        self.assertEqual(failed["owner_kind"], "provider")
        self.assertEqual(failed["failed_check_at"], failed["expires_at"])
        self.assertEqual(failed["checks"], 2)
        self.assertTrue(failed["failed_check_stack"])
        text = json.dumps(observer.snapshot())
        for private in ("DO-NOT-RECORD", DIGEST, "fixture-build@1"):
            self.assertNotIn(private, text)
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_metadata_failure_preserves_original_cancellation(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        value = request()
        authorization = grant(value)
        primary = KeyboardInterrupt("original cancellation")
        original = BuildAuthorization.require_valid
        with mock.patch.object(
            BuildAuthorization, "require_valid", side_effect=primary
        ):
            with mock.patch.object(
                observer, "_stack", side_effect=RuntimeError("diagnostic failed")
            ):
                with self.assertRaises(KeyboardInterrupt) as failure:
                    with observer.observe():
                        authorization.require_valid(value, now=authorization.expires_at)
        self.assertIs(failure.exception, primary)
        self.assertTrue(observer.snapshot()["capture_incomplete"])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_sampling_failure_does_not_change_body_or_restore(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        original = BuildAuthorization.require_valid
        reached = []
        with mock.patch.object(
            diagnostic, "_FRAMES", side_effect=RuntimeError("sample failed")
        ):
            with observer.observe():
                observer._capture(observer._sample)
                reached.append(True)
                observer.record_lifecycle_cleanup(True)
        self.assertEqual(reached, [True])
        self.assertTrue(observer.snapshot()["capture_incomplete"])
        self.assertTrue(observer.snapshot()["cleanup_complete"])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_frame_references_do_not_retain_local_payload(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)

        class Payload:
            pass

        def local_scope():
            payload = Payload()
            reference = weakref.ref(payload)
            observer._sample()
            return reference

        with observer.observe():
            reference = local_scope()
            gc.collect()
            self.assertIsNone(reference())

    def test_metadata_limits_and_snapshot_detachment(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        for index in range(512):
            observer._rows[
                ("src/literate_ai/" + "a" * 160 + str(index) + ".py", "fixture", 1)
            ] = [1, 1]
        value = request()
        now = datetime(2026, 11, 19, tzinfo=UTC)
        for index in range(65):
            observer._grant(grant(value, str(index)), value, now, "passed", [])
        with observer.observe():
            observer._sample()
        report = observer.snapshot()
        self.assertLessEqual(len(json.dumps(report).encode()), 32768)
        self.assertLessEqual(len(observer._rows), 512)
        self.assertLessEqual(len(observer._grants), 64)
        self.assertGreater(report["dropped_frame_samples"], 0)
        self.assertGreater(report["dropped_grants"], 0)
        report["grants"][0]["owner_kind"] = "changed"
        self.assertNotEqual(observer.snapshot()["grants"][0]["owner_kind"], "changed")

    def test_other_thread_grant_calls_are_only_original_delegations(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        value = request()
        authorization = grant(value)
        outcomes = []
        original = BuildAuthorization.require_valid

        def worker():
            authorization.require_valid(value, now=authorization.issued_at)
            try:
                authorization.require_valid(value, now=authorization.expires_at)
            except AuthorizationError as error:
                outcomes.append(error.code)

        with mock.patch.object(
            BuildAuthorization, "require_valid", wraps=original
        ) as delegate:
            with observer.observe():
                thread = threading.Thread(target=worker)
                thread.start()
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())
                observer.record_lifecycle_cleanup(True)
            self.assertEqual(delegate.call_count, 2)
        self.assertEqual(outcomes, ["security.authorization_expired"])
        self.assertEqual(observer.snapshot()["grants"], [])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_secondary_metadata_baseexception_cannot_mask_original(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        value = request()
        authorization = grant(value)
        primary = AuthorizationError("security.authorization_expired")
        original = BuildAuthorization.require_valid
        with mock.patch.object(
            BuildAuthorization, "require_valid", side_effect=primary
        ):
            with mock.patch.object(
                observer, "_grant", side_effect=SystemExit("metadata")
            ):
                with self.assertRaises(AuthorizationError) as failure:
                    with observer.observe():
                        authorization.require_valid(value, now=authorization.expires_at)
        self.assertIs(failure.exception, primary)
        self.assertTrue(observer.snapshot()["capture_incomplete"])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_secondary_startup_baseexception_does_not_replace_body(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        primary = ValueError("original body")
        with mock.patch.object(
            threading.Thread, "start", side_effect=SystemExit("startup")
        ):
            with self.assertRaises(ValueError) as failure:
                with observer.observe():
                    raise primary
        self.assertIs(failure.exception, primary)
        self.assertTrue(observer.snapshot()["capture_incomplete"])

    def test_secondary_cleanup_baseexception_does_not_replace_body(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        primary = ValueError("original body")
        original = BuildAuthorization.require_valid
        with mock.patch.object(
            threading.Thread, "join", side_effect=KeyboardInterrupt("cleanup")
        ):
            with self.assertRaises(ValueError) as failure:
                with observer.observe():
                    raise primary
        observer._stop.set()
        observer._thread.join(timeout=2)
        self.assertFalse(observer._thread.is_alive())
        self.assertIs(failure.exception, primary)
        self.assertTrue(observer.snapshot()["capture_incomplete"])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_false_or_unknown_lifecycle_cleanup_never_reports_complete(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        with observer.observe():
            observer.record_lifecycle_cleanup(False)
            observer.record_lifecycle_cleanup(True)
        report = observer.snapshot()
        self.assertFalse(report["cleanup_complete"])
        self.assertFalse(report["lifecycle_cleanup_complete"])
        self.assertTrue(report["observer_cleanup_complete"])
        self.assertTrue(report["capture_incomplete"])

    def test_startup_failure_and_single_use_are_explicit(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        reached = []
        with mock.patch.object(
            threading.Thread, "start", side_effect=RuntimeError("startup failed")
        ):
            with observer.observe():
                reached.append(True)
        self.assertEqual(reached, [True])
        report = observer.snapshot()
        self.assertTrue(report["capture_incomplete"])
        self.assertFalse(report["capture_active"])
        with self.assertRaises(ValueError):
            with observer.observe():
                self.fail("used diagnostics cannot restart")

    def test_sampling_only_keeps_original_namespace_and_accepts_fixed_factory(self):
        from literate_ai.adapters import node_sdk_verifier_authority as membership
        from literate_ai.adapters import node_sdk_verifier_authorization as authority
        from tests.smoke.test_node_sdk_cross_language import with_provider

        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        original = BuildAuthorization.require_valid
        with tempfile.TemporaryDirectory() as temporary:
            _, snapshot, execution = with_provider(Path(temporary))
            with observer.observe(observe_grants=False):
                self.assertIs(BuildAuthorization.require_valid, original)
                handle = authority.acknowledge_node_sdk_verifier_execution(
                    snapshot=snapshot,
                    execution=execution,
                    actor="isolated sampling control",
                    reason="unchanged fixed namespace",
                    authorization_lifetime=timedelta(minutes=1),
                    authorization_deadline=datetime.now(UTC) + timedelta(minutes=2),
                    acknowledge_identity_only_inputs=True,
                )
                try:
                    authority._original_owner(handle)
                    self.assertIs(BuildAuthorization.require_valid, original)
                    observer._sample()
                finally:
                    membership._retire_acknowledgement(handle)
                observer.record_lifecycle_cleanup(True)
        report = observer.snapshot()
        self.assertFalse(report["qualified"])
        self.assertFalse(report["grant_observation_enabled"])
        self.assertEqual(report["grants"], [])
        self.assertTrue(report["cleanup_complete"])
        self.assertIs(BuildAuthorization.require_valid, original)

    def test_sampling_only_cancellation_never_replaces_original_grant_method(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        original = BuildAuthorization.require_valid
        primary = KeyboardInterrupt("isolated sampling cancelled")
        with self.assertRaises(KeyboardInterrupt) as caught:
            with observer.observe(observe_grants=False):
                self.assertIs(BuildAuthorization.require_valid, original)
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertIs(BuildAuthorization.require_valid, original)
        report = observer.snapshot()
        self.assertFalse(report["grant_observation_enabled"])
        self.assertEqual(report["grants"], [])
        self.assertFalse(report["capture_active"])
        self.assertTrue(report["observer_cleanup_complete"])
        self.assertFalse(report["lifecycle_cleanup_complete"])

    def test_sampling_mode_refuses_truthiness_before_observation(self):
        class Mode:
            def __bool__(self):
                raise AssertionError("foreign mode truthiness invoked")

        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        original = BuildAuthorization.require_valid
        for value in (None, 0, 1, Mode()):
            with self.assertRaises(TypeError):
                with observer.observe(observe_grants=value):
                    self.fail("foreign mode entered observation")
        self.assertFalse(observer._used)
        self.assertIs(BuildAuthorization.require_valid, original)

    def _drive_original_typed_diagnostic(self, scenario, observer, persist):
        from contextlib import ExitStack

        from tests.smoke import test_node_sdk_typed_host_diagnostic as driver

        case = driver.TypedHostSamplingDiagnosticTests(
            "test_original_typed_runtime_sampling_without_qualification"
        )
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(
                    os.environ,
                    {"LITAI_NODE_SDK_RUNTIME_DIAGNOSTIC_OUTPUT": "unused-control.json"},
                )
            )
            stack.enter_context(
                mock.patch.object(
                    driver,
                    "diagnostic_output_path",
                    return_value=ROOT / "unused-control.json",
                )
            )
            stack.enter_context(
                mock.patch.object(driver, "SDKRuntimeDiagnostic", return_value=observer)
            )
            stack.enter_context(
                mock.patch.object(
                    driver.fixture, "CanonicalSDKRuntimeTests", return_value=scenario
                )
            )
            stack.enter_context(
                mock.patch.object(
                    driver, "persist_runtime_diagnostic", side_effect=persist
                )
            )
            case.test_original_typed_runtime_sampling_without_qualification()

    def test_driver_cleanup_failure_is_primary_inside_unrelated_outer_exception(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        scenario = mock.Mock()
        scenario._exercise_authored_runtime.return_value = None
        cleanup = RuntimeError("original isolated scenario cleanup failed")
        scenario.doCleanups.side_effect = cleanup
        recorded = []
        outer = ValueError("unrelated outer caller failure")
        try:
            raise outer
        except ValueError:
            with self.assertRaises(RuntimeError) as caught:
                self._drive_original_typed_diagnostic(
                    scenario,
                    observer,
                    lambda _root, _path, report: recorded.append(report),
                )
        self.assertIs(caught.exception, cleanup)
        self.assertEqual(len(recorded), 1)
        self.assertTrue(recorded[0]["capture_incomplete"])
        self.assertFalse(recorded[0]["lifecycle_cleanup_complete"])
        self.assertFalse(recorded[0]["grant_observation_enabled"])

    def test_driver_preserves_scenario_cancellation_over_cleanup_and_persistence(self):
        observer = diagnostic.SDKRuntimeDiagnostic(ROOT)
        scenario = mock.Mock()
        primary = KeyboardInterrupt("original isolated scenario cancellation")
        scenario._exercise_authored_runtime.side_effect = primary
        scenario.doCleanups.side_effect = RuntimeError("later cleanup failed")
        original = BuildAuthorization.require_valid
        with self.assertRaises(KeyboardInterrupt) as caught:
            self._drive_original_typed_diagnostic(
                scenario,
                observer,
                mock.Mock(side_effect=OSError("metadata unavailable")),
            )
        self.assertIs(caught.exception, primary)
        self.assertIs(BuildAuthorization.require_valid, original)
        report = observer.snapshot()
        self.assertTrue(report["capture_incomplete"])
        self.assertFalse(report["cleanup_complete"])
        self.assertFalse(report["lifecycle_cleanup_complete"])
        self.assertFalse(report["grant_observation_enabled"])
        self.assertEqual(report["grants"], [])
