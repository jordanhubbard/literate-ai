"""Real child-process lease peers; no cloud resources or SSH targets are used."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from literate_ai.adapters import worker_lease_management as leases
from literate_ai.adapters import worker_provisioning as provisioner
from literate_ai.adapters.execution_dispatch import ExecutionDispatchAdapterError
from literate_ai.adapters.worker_registry import change_registry, read_registry
from literate_ai.cli.dispatch import main
from literate_ai.contracts import (
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerCatalog,
    ExecutionWorkerKind,
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
