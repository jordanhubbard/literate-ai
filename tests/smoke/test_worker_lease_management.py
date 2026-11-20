"""Real child-process lease peers; no cloud resources or SSH targets are used."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai.adapters import worker_lease_dispatch as lease_dispatch
from literate_ai.adapters import worker_lease_management as leases
from literate_ai.adapters import worker_provisioning as provisioner
from literate_ai.adapters.execution_dispatch import (
    ExecutionDispatchAdapterError,
    SshExecutionDispatcher,
)
from literate_ai.adapters.worker_registry import change_registry, read_registry
from literate_ai.cli.dispatch import main
from literate_ai.contracts import (
    ContentIdentity,
    ContentReference,
    DispatchResultStatus,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerCatalog,
    ExecutionWorkerKind,
    LifecycleDispatchAction,
    ObservedExecutionEnvironment,
)
from literate_ai.contracts.worker_provisioning import WorkerProvisioner
from literate_ai.schema_catalog import verify_schema_catalog


class WorkerLeaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / "provisioner.json"
        self.state = self.root / "state"
        self.catalog = self.root / "workers.json"
        self.mode = self.root / "mode"
        self.script = (
            Path(__file__).resolve().parents[1]
            / "support/fixtures_worker_lease_peer.py"
        )
        self.worker = ExecutionWorker(
            "lease-worker",
            ExecutionWorkerKind.SSH,
            endpoint="user@example.invalid",
            workspace="~/litai",
        )
        (self.root / "worker.json").write_text(json.dumps(self.worker.to_dict()))
        self.settings = WorkerProvisioner(
            (sys.executable, str(self.script), str(self.root), "allocate"),
            enabled=True,
            timeout_seconds=1,
            management_command=(
                sys.executable,
                str(self.script),
                str(self.root),
                "manage",
            ),
        )
        provisioner.configure(self.config, self.settings)

    def launch(self):
        return provisioner.provision(
            self.config,
            self.state,
            self.catalog,
            "lease-worker",
            "allocation-one",
            ExecutionRequirements(),
            "host",
            {},
            os.environ,
        )

    def manage(self, operation="observe", **kwargs):
        return leases.manage_lease(
            self.config,
            self.state,
            "lease-worker",
            os.environ,
            operation=operation,
            **kwargs,
        )

    def calls(self):
        return [
            json.loads(line) for line in (self.root / "calls").read_text().splitlines()
        ]

    def record(self):
        return provisioner.read_record(
            provisioner.operation_path(self.state, "lease-worker")
        )

    def dispatch_fixture(
        self, execute, *, timeout_seconds=30, terminal=False, exit_status=0, damage=None
    ):
        self.config = self.root / "config/worker-provisioner.json"
        self.state = self.root / "state/worker-provisioning"
        provisioner.configure(self.config, self.settings)
        self.launch()
        worker = read_registry(self.catalog).workers[0]
        identity = ContentIdentity.parse_uri("sha256:" + "1" * 64)
        request = ExecutionDispatchRequest(
            LifecycleDispatchAction.RUN if terminal else LifecycleDispatchAction.BUILD,
            "component://fixture/app",
            "components/app",
            worker.target_profile,
            (),
            worker.identity,
            worker.requirements,
            (),
            (),
            identity,
            identity,
            identity,
            identity,
            identity,
            identity,
            identity,
            ContentReference(
                "artifact-export", "litai-worker-cas:" + identity.uri, identity
            )
            if terminal
            else None,
            timeout_seconds,
        )
        self.dispatch_request = request
        result = ExecutionDispatchResult(
            request.identity,
            worker.identity,
            None,
            DispatchResultStatus.FAILED,
            ObservedExecutionEnvironment("linux", "fixture", "x86_64", 1, 1024),
            1,
            None,
            identity,
        )

        self.dispatch_result = result

        def handler(*_args, **_kwargs):
            execute()
            if terminal:
                from tests.support.fixtures_terminal_managed_run import (
                    imported_run_result,
                )

                imported = imported_run_result(
                    self.root, worker, request, result, exit_status=exit_status
                )
                return (
                    replace(imported, custody_receipt=None)
                    if damage == "receipt"
                    else imported
                )
            return result

        self.terminal_release = (
            lease_dispatch.TerminalManagedRunRelease(timeout_seconds)
            if terminal
            else None
        )
        dispatcher = SshExecutionDispatcher(
            SimpleNamespace(execute=handler),
            environment={
                **os.environ,
                "LITAI_CONFIG_DIR": str(self.root / "config"),
                "LITAI_STATE_DIR": str(self.root / "state"),
            },
            **({} if not terminal else {"terminal_release": self.terminal_release}),
        )
        return lambda: dispatcher.dispatch(worker, request, cwd=self.root)

    def test_terminal_admission_lock_deadline_refuses_before_worker_or_provider(self):
        dispatch = self.dispatch_fixture(
            lambda: self.fail("worker must not run"), timeout_seconds=120, terminal=True
        )
        lock = provisioner.operation_path(self.state, "lease-worker").with_suffix(
            ".lock"
        )
        locked, finish = Event(), Event()

        def hold_lock():
            with exclusive_cache_lock(lock):
                locked.set()
                if not finish.wait(5):
                    raise AssertionError("test lock was not released")

        original_calls = (self.root / "calls").read_bytes()
        with ThreadPoolExecutor(max_workers=1) as pool:
            holder = pool.submit(hold_lock)
            try:
                self.assertTrue(locked.wait(5))
                self.terminal_release.deadline_monotonic = time.monotonic() + 0.05
                with self.assertRaises(ExecutionDispatchAdapterError) as raised:
                    dispatch()
                self.assertEqual(
                    raised.exception.code, "worker.provisioner_lock_unavailable"
                )
                self.assertEqual((self.root / "calls").read_bytes(), original_calls)
                self.assertFalse((self.root / "released").exists())
                self.assertFalse((self.root / "application-runs").exists())
            finally:
                finish.set()
            holder.result(timeout=5)
        self.assertIsNone(self.record().get("dispatch"))

    def test_terminal_budget_reserves_provider_timeout_before_application_launch(self):
        dispatch = self.dispatch_fixture(
            lambda: self.fail("application must not run"),
            timeout_seconds=5,
            terminal=True,
        )
        calls = (self.root / "calls").read_bytes()
        with self.assertRaises(ExecutionDispatchAdapterError) as raised:
            dispatch()
        self.assertEqual(raised.exception.code, "worker.provisioner_deadline_exceeded")
        self.assertIsNone(self.record().get("dispatch"))
        self.assertIsNone(self.record()["management"]["release_request"])
        self.assertEqual((self.root / "calls").read_bytes(), calls)
        self.assertFalse((self.root / "application-runs").exists())
        self.assertFalse((self.root / "released").exists())

    def test_terminal_run_saves_custody_and_release_intent_before_provider_stop(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            result = dispatch()
        record = self.record()
        self.assertEqual(record["status"], "releasing")
        self.assertEqual(record["dispatch"]["state"], "complete")
        self.assertEqual(
            record["dispatch"]["completion"]["custody_receipt_identity"],
            result.custody_receipt.identity.uri,
        )
        self.assertTrue(read_registry(self.catalog).workers)
        self.assertFalse((self.root / "released").exists())
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        self.terminal_release.release()
        self.assertEqual(self.record()["status"], "released")
        self.assertFalse(read_registry(self.catalog).workers)
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_terminal_failed_application_survives_release(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True, exit_status=7
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            result = dispatch()
        completion = self.record()["dispatch"]["completion"]
        request = self.record()["management"]["release_request"]
        write = leases.write_private

        def fail_final_write(path, record, **kwargs):
            if record["status"] == "released":
                raise OSError("controlled terminal publication failure")
            return write(path, record, **kwargs)

        with patch.object(leases, "write_private", side_effect=fail_final_write):
            with self.assertRaises(ExecutionDispatchAdapterError) as raised:
                self.terminal_release.release()
        self.assertEqual(raised.exception.code, "worker.provisioner_cleanup_pending")
        self.assertEqual(self.record()["dispatch"]["completion"], completion)
        self.assertEqual(self.record()["management"]["release_request"], request)
        self.assertEqual(self.record()["status"], "releasing")
        self.terminal_release.release()
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        self.assertEqual(result.status, DispatchResultStatus.FAILED)
        self.assertEqual(result.exit_status, 7)
        self.assertEqual(self.record()["dispatch"]["completion"]["exit_status"], 7)
        self.assertEqual(self.record()["status"], "released")

    def test_terminal_provider_release_waits_for_active_health_inspection(self):
        from literate_ai.cli.execution_workers import dispatch_with_worker_health_poll

        inspecting, dispatched, completed, finish = (Event() for _ in range(4))

        def application():
            if not inspecting.wait(remaining()):
                raise AssertionError("health inspection did not start")

        dispatch = self.dispatch_fixture(
            application, timeout_seconds=120, terminal=True
        )
        selected = SimpleNamespace(worker=read_registry(self.catalog).workers[0])

        # Startup, child-process custody publication and thread scheduling share
        # the actual terminal operation budget. A separate five-second race on a
        # loaded Windows runner does not measure release/inspection ordering.
        def remaining():
            return max(0.0, self.terminal_release.deadline_monotonic - time.monotonic())

        def dispatch_and_signal():
            result = dispatch()
            dispatched.set()
            return result

        def inspect(*_args, **_kwargs):
            inspecting.set()
            if not dispatched.wait(remaining()):
                raise AssertionError("dispatch did not finish within terminal budget")
            self.assertEqual(self.record()["dispatch"]["state"], "complete")
            self.assertFalse((self.root / "released").exists())
            completed.set()
            if not finish.wait(remaining()):
                raise AssertionError("health inspection was not released")
            self.assertFalse((self.root / "released").exists())
            return {"fixture": "inspection finished"}

        def run_and_release():
            result, polls = dispatch_with_worker_health_poll(
                SimpleNamespace(
                    worker_health_config="fixture", worker_health_poll_seconds=0.01
                ),
                selected,
                self.dispatch_request.identity,
                dispatch_and_signal,
                admission=inspect,
                deadline_monotonic=self.terminal_release.deadline_monotonic,
            )
            self.terminal_release.release()
            return result, polls

        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(run_and_release)
                try:
                    if not completed.wait(remaining()):
                        if running.done():
                            running.result()
                        self.fail(
                            "health inspection did not observe completed dispatch"
                        )
                    self.assertFalse(running.done())
                    self.assertFalse((self.root / "released").exists())
                finally:
                    finish.set()
                result, polls = running.result(timeout=remaining())
        self.assertEqual(result.exit_status, 0)
        self.assertEqual(len(polls), 1)
        self.assertEqual(self.record()["status"], "released")
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")

    def test_terminal_controller_exit_recovers_saved_completion_without_rerun(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True
        )
        payload = self.root / "controller.json"
        payload.write_text(
            json.dumps(
                {
                    "root": str(self.root),
                    "worker": read_registry(self.catalog).workers[0].to_dict(),
                    "request": self.dispatch_request.to_dict(),
                    "result": self.dispatch_result.to_dict(),
                }
            )
        )
        environment = {
            **os.environ,
            "LITAI_CONFIG_DIR": str(self.root / "config"),
            "LITAI_STATE_DIR": str(self.root / "state"),
            "OBJ_DIR": str(self.root / "objects"),
        }
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.support.fixtures_terminal_managed_run",
                str(payload),
            ],
            env=environment,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(child.returncode, 23, child.stderr.decode())
        saved = self.record()
        self.assertEqual(saved["dispatch"]["state"], "complete")
        self.assertEqual(saved["status"], "releasing")
        self.assertFalse((self.root / "released").exists())
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        output = io.StringIO()
        with patch.dict(os.environ, environment):
            status = main(
                [
                    "worker",
                    "provisioner",
                    "release",
                    "lease-worker",
                    "--acknowledge",
                    "--json",
                ],
                stdout=output,
                stderr=output,
            )
        self.assertEqual(status, 0, output.getvalue())
        recovered = self.record()
        self.assertEqual(recovered["status"], "released")
        self.assertEqual(
            recovered["dispatch"]["completion"], saved["dispatch"]["completion"]
        )
        self.assertEqual(
            recovered["management"]["release_request"],
            saved["management"]["release_request"],
        )
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_terminal_initial_completion_write_failure_keeps_active_fence(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True
        )
        write = lease_dispatch.write_private

        def fail_completion_write(path, record, **kwargs):
            if record.get("dispatch", {}).get("completion") is not None:
                raise OSError("controlled initial completion publication failure")
            return write(path, record, **kwargs)

        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            with patch.object(
                lease_dispatch, "write_private", side_effect=fail_completion_write
            ):
                with self.assertRaisesRegex(OSError, "initial completion publication"):
                    dispatch()
        record = self.record()
        self.assertEqual(record["dispatch"]["state"], "active")
        self.assertNotIn("completion", record["dispatch"])
        self.assertIsNone(record["management"]["release_request"])
        self.assertFalse(self.terminal_release.saved)
        self.assertFalse((self.root / "released").exists())
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.terminal_release.release()
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        self.assertFalse((self.root / "released").exists())
        self.manage("release", cancel_attempt=record["dispatch"]["attempt"])
        self.assertEqual(self.record()["status"], "released")
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_terminal_missing_custody_never_releases(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True, damage="receipt"
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            with self.assertRaises(ExecutionDispatchAdapterError) as raised:
                dispatch()
        self.assertEqual(
            raised.exception.code, "worker.provisioner_completion_custody_missing"
        )
        self.assertEqual(self.record()["dispatch"]["state"], "uncertain")
        self.assertFalse((self.root / "released").exists())
        self.assertIsNone(self.record()["management"]["release_request"])

    def test_terminal_release_rechecks_current_evidence_before_provider_stop(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            dispatch()
        completion = self.record()["dispatch"]["completion"]
        request = self.record()["management"]["release_request"]
        store = Path(completion["store_path"])
        blobs = list((store / "blobs" / "sha256").glob("*/*"))
        self.assertEqual(len(blobs), 1)
        blob = blobs[0]
        original = blob.read_bytes()
        for damaged in (None, bytes([original[0] ^ 1]) + original[1:]):
            with self.subTest(damage="missing" if damaged is None else "corrupt"):
                if damaged is None:
                    blob.unlink()
                else:
                    blob.write_bytes(damaged)
                with self.assertRaises(ExecutionDispatchAdapterError) as raised:
                    self.terminal_release.release()
                self.assertEqual(
                    raised.exception.code,
                    "worker.provisioner_completion_custody_unavailable",
                )
                # The public recovery owner must preserve the custody gate too.
                with self.assertRaises(ExecutionDispatchAdapterError) as recovery:
                    self.manage("release")
                self.assertEqual(
                    recovery.exception.code,
                    "worker.provisioner_completion_custody_unavailable",
                )
                self.assertFalse((self.root / "released").exists())
                self.assertEqual(self.record()["dispatch"]["completion"], completion)
                self.assertEqual(
                    self.record()["management"]["release_request"], request
                )
                self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
                blob.write_bytes(original)
        # Restoring current evidence permits the same pending release; no rebuild
        # or previous TEST artifact is present in this fresh coordinator store.
        self.terminal_release.release()
        self.assertEqual(self.record()["status"], "released")
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")

    def test_terminal_lost_release_reply_recovers_without_running_again(self):
        dispatch = self.dispatch_fixture(
            lambda: None, timeout_seconds=120, terminal=True
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            dispatch()
        completion = self.record()["dispatch"]["completion"]
        request = self.record()["management"]["release_request"]
        self.mode.write_text("lost-release")
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.terminal_release.release()
        self.assertEqual(self.record()["dispatch"]["completion"], completion)
        self.assertEqual(self.record()["management"]["release_request"], request)
        provisioner.configure(self.config, replace(self.settings, enabled=False))
        self.mode.write_text("ok")
        self.assertEqual(self.manage("release")["status"], "released")
        self.assertEqual(self.record()["management"]["release_request"], request)
        self.assertEqual((self.root / "application-runs").read_bytes(), b"x")
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_dispatch_requires_fresh_lease_covering_the_job_deadline(self):
        calls = []
        dispatch = self.dispatch_fixture(lambda: calls.append("job"))
        self.mode.write_text("short")
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "whole job"):
            dispatch()
        self.assertEqual(calls, [])
        self.assertNotIn("dispatch", self.record())
        self.mode.write_text("ok")
        self.assertEqual(dispatch().status, DispatchResultStatus.FAILED)
        first = self.record()["dispatch"]["attempt"]
        self.assertEqual(self.record()["dispatch"]["state"], "complete")
        dispatch()
        self.assertNotEqual(first, self.record()["dispatch"]["attempt"])
        self.assertEqual(calls, ["job", "job"])
        self.mode.write_text("expired")
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        self.assertEqual(calls, ["job", "job"])
        self.assertFalse(read_registry(self.catalog).workers)

    def test_release_drains_active_dispatch_and_blocks_new_admission(self):
        entered, finish = Event(), Event()

        def job():
            entered.set()
            if not finish.wait(5):
                raise AssertionError("fixture was not released")

        dispatch = self.dispatch_fixture(job)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(dispatch)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(
                    ExecutionDispatchAdapterError, "intent is saved"
                ):
                    self.manage("release")
                release = self.record()["management"]["release_request"]
                self.assertEqual(self.record()["status"], "releasing")
                self.assertFalse((self.root / "released").exists())
                with self.assertRaises(ExecutionDispatchAdapterError):
                    dispatch()
            finally:
                finish.set()
            self.assertEqual(
                running.result(timeout=5).status, DispatchResultStatus.FAILED
            )
        self.assertEqual(self.record()["dispatch"]["state"], "complete")
        self.manage("release")
        self.assertEqual(self.record()["management"]["release_request"], release)
        self.assertEqual(self.record()["dispatch"]["state"], "released")

    def test_short_execution_still_reserves_actual_remote_cleanup_waits(self):
        calls = []
        dispatch = self.dispatch_fixture(lambda: calls.append("job"), timeout_seconds=1)
        # Twelve seconds covered the previous incorrect1+10 assumption, but
        # cannot cover the actual remote process owner's configured waits.
        self.mode.write_text("cleanup-short")
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "whole job"):
            dispatch()
        self.assertEqual(calls, [])

    def test_interrupted_dispatch_requires_exact_explicit_cancellation(self):
        def interrupted():
            raise RuntimeError("simulated lost transport")

        dispatch = self.dispatch_fixture(interrupted)
        with self.assertRaisesRegex(RuntimeError, "lost transport"):
            dispatch()
        self.assertEqual(self.record()["dispatch"]["state"], "uncertain")
        attempt = self.record()["dispatch"]["attempt"]
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "intent is saved"):
            self.manage("release")
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "current attempt"):
            self.manage("release", cancel_attempt="0" * 64)
        self.assertFalse((self.root / "released").exists())
        output = io.StringIO()
        with patch.dict(
            os.environ,
            {
                "LITAI_CONFIG_DIR": str(self.root / "config"),
                "LITAI_STATE_DIR": str(self.root / "state"),
            },
        ):
            status = main(
                [
                    "worker",
                    "provisioner",
                    "release",
                    "lease-worker",
                    "--acknowledge",
                    "--cancel-attempt",
                    attempt,
                    "--json",
                ],
                stdout=output,
                stderr=output,
            )
        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(self.record()["dispatch"]["state"], "released")
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)
        self.manage("release", cancel_attempt=attempt)
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "cancelled attempt"):
            self.manage("release", cancel_attempt="0" * 64)
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_terminal_release_cannot_cancel_an_ordinary_completed_job(self):
        dispatch = self.dispatch_fixture(lambda: None)
        dispatch()
        attempt = self.record()["dispatch"]["attempt"]
        self.manage("release")
        count = len(self.calls())
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "cancelled attempt"):
            self.manage("release", cancel_attempt=attempt)
        self.assertEqual(len(self.calls()), count)

    def test_publication_delay_cannot_start_a_job_without_remaining_headroom(self):
        calls = []
        dispatch = self.dispatch_fixture(lambda: calls.append("job"))
        write = lease_dispatch.write_private

        def exercise(delay):
            before, elapsed = datetime.now(UTC), [0]

            def publish(path, record, **kwargs):
                write(path, record, **kwargs)
                if record.get("dispatch", {}).get("state") == "active":
                    elapsed[0] = delay

            clock = SimpleNamespace(
                now=lambda _zone: before + timedelta(seconds=elapsed[0])
            )
            with (
                patch.object(lease_dispatch, "datetime", clock),
                patch.object(lease_dispatch.time, "monotonic", lambda: elapsed[0]),
                patch.object(lease_dispatch, "write_private", publish),
            ):
                with self.assertRaisesRegex(
                    ExecutionDispatchAdapterError, "before launch"
                ):
                    dispatch()
            self.assertEqual(calls, [])
            self.assertEqual(self.record()["dispatch"]["state"], "not-started")

        for delay in (3590, 7200):
            with self.subTest(delay=delay):
                exercise(delay)

    def test_result_after_explicit_lease_cancellation_is_not_accepted(self):
        def cancelled():
            attempt = self.record()["dispatch"]["attempt"]
            self.manage("release", cancel_attempt=attempt)

        dispatch = self.dispatch_fixture(cancelled)
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "invalidated"):
            dispatch()
        self.assertEqual(self.record()["status"], "released")

    def test_controller_process_exit_leaves_a_durable_outstanding_attempt(self):
        dispatch = self.dispatch_fixture(lambda: None)
        dispatch()
        # The new process enters the actual lease gate, then dies without Python
        # cleanup. No SSH connection or remote resource exists in this fixture.
        program = """
import json, os, sys
from pathlib import Path
from literate_ai.adapters.worker_lease_dispatch import admitted_lease_dispatch
from literate_ai.adapters.worker_registry import read_registry
from literate_ai.contracts import ExecutionDispatchRequest
root=Path(sys.argv[1])
worker=read_registry(root/'workers.json').workers[0]
request=ExecutionDispatchRequest.from_dict(
    json.loads((root/'request.json').read_text()))
with admitted_lease_dispatch(
    root/'config/worker-provisioner.json', root/'state/worker-provisioning',
    worker, request, os.environ,
):
    os._exit(23)
"""
        request_record = self.record()["dispatch"]["request_identity"]
        (self.root / "request.json").write_text(
            json.dumps(self.dispatch_request.to_dict())
        )
        child = subprocess.run(
            [sys.executable, "-c", program, str(self.root)],
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(child.returncode, 23, child.stderr.decode())
        record = self.record()
        self.assertEqual(record["dispatch"]["state"], "active")
        self.assertEqual(record["dispatch"]["request_identity"], request_record)
        with self.assertRaises(ExecutionDispatchAdapterError):
            dispatch()
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "intent is saved"):
            self.manage("release")
        self.manage("release", cancel_attempt=record["dispatch"]["attempt"])
        self.assertEqual(self.record()["status"], "released")

    def test_backward_clock_change_does_not_extend_admission(self):
        calls = []
        dispatch = self.dispatch_fixture(lambda: calls.append("job"))
        self.mode.write_text("short")
        before = datetime.now(UTC)
        clock = SimpleNamespace(now=lambda _zone: before - timedelta(hours=2))
        first = True

        def now(_zone):
            nonlocal first
            if first:
                first = False
                return before
            return clock.now(_zone)

        with patch.object(lease_dispatch, "datetime", SimpleNamespace(now=now)):
            with self.assertRaisesRegex(ExecutionDispatchAdapterError, "whole job"):
                dispatch()
        self.assertEqual(calls, [])

    def test_lookup_lost_allocation_reply_recovers_without_allocating_twice(self):
        self.mode.write_text("lost-allocation")
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.launch()
        self.assertEqual(self.record()["status"], "uncertain")
        self.mode.write_text("ok")
        self.assertEqual(self.manage()["status"], "ready")
        self.assertFalse(read_registry(self.catalog).workers)
        provisioner.recover(self.state, "lease-worker")
        self.assertEqual(
            read_registry(self.catalog).workers,
            (provisioner.registered_worker(self.record()),),
        )
        self.assertEqual(self.launch()["status"], "registered")
        self.assertEqual([kind for kind, _ in self.calls()], ["allocate", "manage"])

    def lost_allocation_controller(self):
        self.config = self.root / "config/worker-provisioner.json"
        self.state = self.root / "state/worker-provisioning"
        provisioner.configure(self.config, self.settings)
        environment = {
            **os.environ,
            "LITAI_CONFIG_DIR": str(self.root / "config"),
            "LITAI_STATE_DIR": str(self.root / "state"),
            "LITAI_NO_SELF_UPDATE": "1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        }
        program = """
import os, sys
from literate_ai.adapters import worker_provisioning as provider
from literate_ai.cli.dispatch import main
invoke = provider.invoke

def lose_reply(*args, **kwargs):
    reply = invoke(*args, **kwargs)
    if kwargs.get("request") is not None:
        os._exit(23)
    return reply

provider.invoke = lose_reply
raise SystemExit(main(sys.argv[1:]))
"""
        arguments = (
            "worker",
            "provision",
            "lease-worker",
            "--request-id",
            "allocation-one",
            "--worker-config",
            str(self.catalog),
            "--json",
        )
        child = subprocess.run(
            [sys.executable, "-P", "-c", program, *arguments],
            cwd=self.root,
            env=environment,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(child.returncode, 23, child.stderr.decode())
        self.assertTrue((self.root / "allocation").is_file())
        self.assertEqual(self.record()["status"], "uncertain")
        self.assertIsNone(self.record()["response"])
        static = replace(self.worker, worker_id="static-worker")
        change_registry(self.catalog, lambda _: ExecutionWorkerCatalog((static,)))

        def public(*arguments):
            output = io.StringIO()
            with patch.dict(os.environ, environment):
                status = main(
                    ["worker", "provisioner", *arguments, "--json"],
                    stdout=output,
                    stderr=output,
                )
            value = json.loads(output.getvalue())
            return status, value.get("result", value)

        self.assertEqual(public("disable")[0], 0)
        return public, static

    def test_public_disable_and_absence_require_exact_terminal_acknowledgement(self):
        public, static = self.lost_allocation_controller()
        self.mode.write_text("absent")
        status, result = public("observe", "lease-worker")
        self.assertEqual(status, 0, result)
        self.assertEqual(result["request"]["status"], "uncertain")
        self.assertEqual(
            result["request"]["management"]["response"]["status"], "absent"
        )
        self.assertNotEqual(public("recover", "lease-worker")[0], 0)
        status, failure = public(
            "release", "lease-worker", "--expired-only", "--acknowledge"
        )
        self.assertNotEqual(status, 0)
        self.assertEqual(
            failure["error"]["code"], "worker.provisioner_lease_not_expired"
        )
        self.mode.write_text("ok")
        status, result = public("release", "lease-worker", "--acknowledge")
        self.assertEqual(status, 0, result)
        self.assertEqual(result["request"]["status"], "released")
        self.assertIsNone(result["request"]["management"]["request"]["lease_id"])
        self.assertNotIn("dispatch", result["request"])
        self.assertEqual(public("release", "lease-worker", "--acknowledge")[0], 0)
        self.assertEqual(
            [kind for kind, _ in self.calls()], ["allocate", "manage", "manage"]
        )
        self.assertEqual(read_registry(self.catalog).workers, (static,))
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_public_expired_generation_survives_rollback_and_absent_lookup(self):
        public, static = self.lost_allocation_controller()
        self.mode.write_text("expired")
        status, result = public("observe", "lease-worker")
        self.assertEqual(status, 0, result)
        self.assertEqual(read_registry(self.catalog).workers, (static,))
        rolled_back = datetime.now(UTC) - timedelta(hours=2)
        with patch.object(
            leases,
            "datetime",
            SimpleNamespace(
                now=lambda _zone: rolled_back, fromisoformat=datetime.fromisoformat
            ),
        ):
            status, recovery = public("recover", "lease-worker")
            self.assertNotEqual(status, 0, recovery)
            self.mode.write_text("ok")
            status, result = public("observe", "lease-worker")
            self.assertEqual(status, 0, result)
            self.assertEqual(result["request"]["status"], "expired")
            self.assertNotEqual(public("recover", "lease-worker")[0], 0)
        self.mode.write_text("wrong-lease")
        self.assertNotEqual(public("observe", "lease-worker")[0], 0)
        self.assertEqual(self.record()["status"], "expired")
        self.mode.write_text("absent")
        status, result = public("observe", "lease-worker")
        self.assertEqual(status, 0, result)
        self.assertEqual(result["request"]["status"], "expired")
        self.mode.write_text("ok")
        status, result = public(
            "release", "lease-worker", "--expired-only", "--acknowledge"
        )
        self.assertEqual(status, 0, result)
        record = result["request"]
        self.assertEqual(record["status"], "released")
        self.assertEqual(record["management"]["request"]["lease_id"], "lease-one")
        self.assertNotIn("dispatch", record)
        self.assertEqual(
            public("release", "lease-worker", "--expired-only", "--acknowledge")[0], 0
        )
        self.assertEqual([kind for kind, _ in self.calls()].count("allocate"), 1)
        self.assertEqual(read_registry(self.catalog).workers, (static,))
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_release_survives_lost_reply_and_uses_one_idempotency_key(self):
        self.launch()
        self.mode.write_text("lost-release")
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.manage("release")
        release = self.record()["management"]["release_request"]
        self.assertEqual(self.record()["status"], "releasing")
        self.assertFalse(read_registry(self.catalog).workers)
        with self.assertRaises(ExecutionDispatchAdapterError):
            provisioner.recover(self.state, "lease-worker")
        self.mode.write_text("ok")
        self.assertEqual(self.manage("release")["status"], "released")
        self.assertEqual(self.record()["management"]["request"], release)
        self.manage("release")
        self.assertEqual(len(self.calls()), 3)
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.launch()
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "cancelled attempt"):
            self.manage("release", cancel_attempt="0" * 64)

    def test_observing_after_release_failure_preserves_release_intent(self):
        self.launch()
        self.mode.write_text("lost-release")
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.manage("release")
        release = self.record()["management"]["release_request"]
        self.mode.write_text("ok")
        self.assertEqual(self.manage()["status"], "releasing")
        with self.assertRaises(ExecutionDispatchAdapterError):
            provisioner.recover(self.state, "lease-worker")
        self.manage("release")
        self.assertEqual(self.record()["management"]["request"], release)

    def test_pending_release_and_failed_terminal_write_keep_the_same_request(self):
        self.launch()
        self.mode.write_text("pending")
        self.assertEqual(self.manage("release")["status"], "releasing")
        release = self.record()["management"]["release_request"]
        self.mode.write_text("ok")
        original_write = leases.write_private

        def interrupted(path, record, **kwargs):
            if record["status"] == "released":
                raise OSError("simulated publication failure")
            return original_write(path, record, **kwargs)

        with patch.object(leases, "write_private", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.manage("release")
        self.assertEqual(self.record()["status"], "releasing")
        self.assertEqual(self.manage("release")["status"], "released")
        self.assertEqual(self.record()["management"]["request"], release)
        self.assertEqual(len(json.loads((self.root / "released").read_text())), 1)

    def test_concurrent_release_calls_do_not_repeat_provider_operation(self):
        self.launch()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.manage("release"), range(2)))
        self.assertTrue(all(result["status"] == "released" for result in results))
        self.assertEqual(len(self.calls()), 2)

    def test_disabled_allocation_still_permits_recorded_lease_cleanup(self):
        self.launch()
        provisioner.configure(self.config, enabled=False)
        self.manage()
        self.assertEqual(self.manage("release")["status"], "released")

    def test_changed_config_or_registration_cannot_release_another_owner(self):
        self.launch()
        provisioner.configure(self.config, replace(self.settings, timeout_seconds=2))
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "configuration"):
            self.manage("release")
        self.assertEqual(len(self.calls()), 1)
        provisioner.configure(self.config, self.settings)
        foreign = replace(self.worker, endpoint="another@example.invalid")
        change_registry(self.catalog, lambda _: ExecutionWorkerCatalog((foreign,)))
        with self.assertRaisesRegex(
            ExecutionDispatchAdapterError, "registration changed"
        ):
            self.manage("release")
        self.assertEqual(read_registry(self.catalog).workers, (foreign,))
        self.assertEqual(len(self.calls()), 1)

    def test_static_registration_without_a_record_has_no_cleanup_authority(self):
        change_registry(self.catalog, lambda _: ExecutionWorkerCatalog((self.worker,)))
        with self.assertRaises(ExecutionDispatchAdapterError):
            self.manage("release")
        self.assertFalse((self.root / "calls").exists())
        self.assertEqual(read_registry(self.catalog).workers, (self.worker,))

    def test_identical_static_replacement_is_not_the_provisioned_registration(self):
        self.launch()
        managed = read_registry(self.catalog).workers[0]
        self.assertIsNotNone(managed.provisioning_identity)
        self.assertEqual(ExecutionWorker.from_dict(managed.to_dict()), managed)
        change_registry(self.catalog, lambda _: ExecutionWorkerCatalog((self.worker,)))
        with self.assertRaisesRegex(
            ExecutionDispatchAdapterError, "registration changed"
        ):
            self.manage("release")
        self.assertEqual(read_registry(self.catalog).workers, (self.worker,))
        self.assertEqual(len(self.calls()), 1)

    def test_expired_observation_blocks_recovery_and_allows_expired_only_release(self):
        self.launch()
        self.manage()
        with self.assertRaisesRegex(ExecutionDispatchAdapterError, "expired"):
            self.manage("release", expired_only=True)
        self.mode.write_text("expired")
        self.manage()
        self.assertFalse(read_registry(self.catalog).workers)
        with self.assertRaises(ExecutionDispatchAdapterError):
            provisioner.recover(self.state, "lease-worker")
        self.mode.write_text("ok")
        self.assertEqual(
            self.manage("release", expired_only=True)["status"], "released"
        )

    def test_missing_or_pending_worker_never_re_registers(self):
        self.launch()
        for mode in ("pending", "absent"):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                self.assertEqual(self.manage()["status"], "uncertain")
                self.assertFalse(read_registry(self.catalog).workers)
                with self.assertRaises(ExecutionDispatchAdapterError):
                    provisioner.recover(self.state, "lease-worker")

    def test_stale_or_different_lease_replies_do_not_authorize_recovery(self):
        self.launch()
        self.manage()
        for mode in ("replay", "wrong-lease", "wrong-request", "bad-expiry"):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                with self.assertRaises((ExecutionDispatchAdapterError, ValueError)):
                    self.manage()
                self.assertEqual(self.record()["management"]["state"], "pending")
                with self.assertRaises(ExecutionDispatchAdapterError):
                    provisioner.recover(self.state, "lease-worker")
        self.assertEqual(sum(kind == "allocate" for kind, _ in self.calls()), 1)

    def test_management_process_limits_and_configuration_drift_preserve_intent(self):
        self.launch()
        for mode in ("timeout", "overflow", "config-drift"):
            with self.subTest(mode=mode):
                self.mode.write_text(mode)
                with self.assertRaises(ExecutionDispatchAdapterError):
                    self.manage()
                self.assertEqual(self.record()["management"]["state"], "pending")

    def test_public_cli_requires_release_acknowledgement(self):
        from literate_ai.cli import worker_provisioning as cli

        self.launch()
        paths = SimpleNamespace(
            worker_provisioner=self.config, worker_provisioning=self.state
        )

        def call(*arguments):
            output = io.StringIO()
            with patch.object(cli, "resolve_user_paths", return_value=paths):
                status = main(
                    ["worker", "provisioner", *arguments, "--json"],
                    stdout=output,
                    stderr=output,
                )
            return status, json.loads(output.getvalue())

        self.assertNotEqual(call("release", "lease-worker")[0], 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(call("observe", "lease-worker")[0], 0)
        status, value = call("release", "lease-worker", "--acknowledge")
        self.assertEqual(status, 0, value)
        self.assertEqual(value["result"]["request"]["status"], "released")

    def test_configuration_and_management_requests_match_published_schema(self):
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "schemas/v2/worker-provisioning.schema.json"
            ).read_text()
        )
        Draft202012Validator.check_schema(schema)
        directory = Path(__file__).resolve().parents[2] / "schemas/v2"
        verify_schema_catalog("v2", directory)
        registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document))
            for path in directory.glob("*.schema.json")
            if "$id" in (document := json.loads(path.read_text()))
        )
        config = Draft202012Validator(
            schema["$defs"]["configuration"], registry=registry
        )
        config.validate(self.settings.to_dict())
        self.assertFalse(
            config.is_valid(dict(self.settings.to_dict(), management_command=[]))
        )
        self.assertEqual(
            WorkerProvisioner.from_dict(self.settings.to_dict()), self.settings
        )
        self.launch()
        self.manage()
        validator = Draft202012Validator(
            schema["$defs"]["lease_request"], registry=registry
        )
        validator.validate(self.calls()[-1][1])
        response_validator = Draft202012Validator(
            schema["$defs"]["lease_response"], registry=registry
        )
        response_validator.validate(self.record()["management"]["response"])
        self.manage("release")
        validator.validate(self.calls()[-1][1])
        response_validator.validate(self.record()["management"]["response"])
